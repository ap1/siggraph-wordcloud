"""Build paper-title word clouds for graphics and vision conferences."""

from __future__ import annotations

import argparse
import collections
import html
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
import os
from pathlib import Path
import re
import tempfile
import time
import unicodedata
from typing import Callable, Iterable, Sequence
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# CVF Open Access currently returns HTTP 406 to non-browser user-agent strings.
# This conservative browser profile is also accepted by Ke-Sen's indexes.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_DELAY_SECONDS = 0.5
DEFAULT_TOP_WORDS = 10
WORD_LIST_SIZE = 500

# Lowercase/casefolded terms that add little meaning to a title trend chart.
COMMON_WORDS = frozenset(
    {
        "3d",
        "a",
        "an",
        "and",
        "by",
        "design",
        "for",
        "from",
        "graphics",
        "in",
        "is",
        "of",
        "on",
        "or",
        "the",
        "to",
        "using",
        "via",
        "with",
    }
)

TOKEN_PATTERN = re.compile(r"[^\W_]+(?:['-][^\W_]+)*", re.UNICODE)
UNICODE_HYPHENS = re.compile(r"[\u2010\u2011]")
UNICODE_DASHES = re.compile(r"[\u2012-\u2015\u2212]")


@dataclass(frozen=True)
class Conference:
    slug: str
    title: str
    first_year: int
    parser: str
    source_name: str
    source_home: str
    year_url: Callable[[int], str]


@dataclass(frozen=True)
class YearResult:
    year: int
    source_url: str
    paper_count: int
    words: tuple[str, ...]
    top_words: tuple[tuple[str, int], ...]


def cvpr_url(year: int) -> str:
    return f"https://openaccess.thecvf.com/CVPR{year}?day=all"


def kesen_url(prefix: str, suffix: str, year: int) -> str:
    return f"https://kesen.realtimerendering.com/{prefix}{year}{suffix}"


CONFERENCES: dict[str, Conference] = {
    "sig": Conference(
        "sig",
        "SIGGRAPH",
        2008,
        "kesen",
        "Ke-Sen Huang's paper index",
        "https://kesen.realtimerendering.com/",
        lambda year: kesen_url("sig", ".html", year),
    ),
    "siga": Conference(
        "siga",
        "SIGGRAPH Asia",
        2008,
        "kesen",
        "Ke-Sen Huang's paper index",
        "https://kesen.realtimerendering.com/",
        lambda year: kesen_url("siga", "Papers.htm", year),
    ),
    "cvpr": Conference(
        "cvpr",
        "CVPR",
        2013,
        "cvpr",
        "CVF Open Access",
        "https://openaccess.thecvf.com/",
        cvpr_url,
    ),
    "hpg": Conference(
        "hpg",
        "High-Performance Graphics",
        2009,
        "kesen",
        "Ke-Sen Huang's paper index",
        "https://kesen.realtimerendering.com/",
        lambda year: kesen_url("hpg", "Papers.htm", year),
    ),
    "egsr": Conference(
        "egsr",
        "Eurographics Symposium on Rendering",
        2009,
        "kesen",
        "Ke-Sen Huang's paper index",
        "https://kesen.realtimerendering.com/",
        lambda year: kesen_url("egsr", "Papers.htm", year),
    ),
}


class PaperTitleParser(HTMLParser):
    """Extract titles from either CVF or Ke-Sen's lightweight indexes."""

    def __init__(self, source_format: str) -> None:
        super().__init__(convert_charrefs=True)
        if source_format not in {"cvpr", "kesen"}:
            raise ValueError(f"Unknown paper index format: {source_format}")
        self.source_format = source_format
        self.titles: list[str] = []
        self._in_candidate = False
        self._capture_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        attributes = {key.casefold(): value or "" for key, value in attrs}

        if self.source_format == "cvpr":
            classes = attributes.get("class", "").casefold().split()
            if tag == "dt" and "ptitle" in classes:
                self._in_candidate = True
            if self._in_candidate:
                self._capture_depth += 1
            return

        if tag == "dt":
            self._in_candidate = True
        if self._in_candidate and tag == "b":
            self._capture_depth = 1
        elif self._capture_depth:
            self._capture_depth += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()

        if self.source_format == "cvpr":
            if self._in_candidate:
                self._capture_depth = max(0, self._capture_depth - 1)
            if tag == "dt" and self._in_candidate:
                self._finish_title()
            return

        if self._capture_depth:
            self._capture_depth -= 1
            if tag == "b" and self._capture_depth == 0:
                self._finish_title()
        if tag == "dt":
            self._in_candidate = False

    def handle_data(self, data: str) -> None:
        if self._capture_depth:
            self._parts.append(data)

    def _finish_title(self) -> None:
        title = " ".join(" ".join(self._parts).split())
        if title:
            self.titles.append(title)
        self._parts.clear()
        self._capture_depth = 0
        self._in_candidate = False


class CvprDayLinkParser(HTMLParser):
    """Collect legacy CVPR daily-program links from a year landing page."""

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a":
            return
        href = next((value for key, value in attrs if key.casefold() == "href"), None)
        if not href:
            return
        absolute_url = urljoin(self.base_url, href)
        parsed = urlparse(absolute_url)
        day_values = parse_qs(parsed.query).get("day", [])
        if (
            parsed.hostname == "openaccess.thecvf.com"
            and day_values
            and day_values[0].casefold() != "all"
            and absolute_url not in self.urls
        ):
            self.urls.append(absolute_url)


def parse_paper_titles(page_html: str, source_format: str) -> list[str]:
    parser = PaperTitleParser(source_format)
    parser.feed(page_html)
    parser.close()
    return parser.titles


def parse_cvpr_day_urls(page_html: str, base_url: str) -> list[str]:
    parser = CvprDayLinkParser(base_url)
    parser.feed(page_html)
    parser.close()
    return parser.urls


def title_words(titles: Iterable[str]) -> list[str]:
    words: list[str] = []
    for title in titles:
        normalized = unicodedata.normalize("NFKC", html.unescape(title))
        normalized = UNICODE_HYPHENS.sub("-", normalized)
        normalized = UNICODE_DASHES.sub(" ", normalized).replace("’", "'")
        words.extend(
            token
            for token in (match.casefold() for match in TOKEN_PATTERN.findall(normalized))
            if token not in COMMON_WORDS
        )
    return words


def top_words(words: Iterable[str], limit: int) -> list[tuple[str, int]]:
    return collections.Counter(words).most_common(limit)


def create_session() -> requests.Session:
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    session = requests.Session()
    # CVF rejects a narrowed HTML Accept header with HTTP 406; requests' */*
    # default works for both sources and still receives an HTML response.
    session.headers.update({"User-Agent": USER_AGENT})
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session


def decode_response(response: requests.Response) -> str:
    encoding = response.encoding
    if not encoding or encoding.casefold() in {"iso-8859-1", "latin-1"}:
        encoding = response.apparent_encoding or "utf-8"
    return response.content.decode(encoding, errors="replace")


def fetch_year(
    session: requests.Session,
    conference: Conference,
    year: int,
    timeout: float,
    top_word_count: int,
) -> YearResult:
    source_url = conference.year_url(year)
    response = session.get(source_url, timeout=timeout)
    response.raise_for_status()
    page_html = decode_response(response)
    titles = parse_paper_titles(page_html, conference.parser)

    # CVPR 2018–2020 have no all-papers view. Their landing page links to one
    # paper index per conference day, while newer and older years expose a
    # single index. Fall back to those daily pages when necessary.
    if not titles and conference.parser == "cvpr":
        source_url = f"https://openaccess.thecvf.com/CVPR{year}"
        landing_response = session.get(source_url, timeout=timeout)
        landing_response.raise_for_status()
        day_urls = parse_cvpr_day_urls(decode_response(landing_response), source_url)
        for day_url in day_urls:
            day_response = session.get(day_url, timeout=timeout)
            day_response.raise_for_status()
            titles.extend(parse_paper_titles(decode_response(day_response), conference.parser))

    # A malformed index should not count the same title twice if it repeats a
    # day link or carries a duplicate listing.
    titles = list(dict.fromkeys(titles))
    if not titles:
        raise ValueError("the page contained no recognizable paper titles")

    words = title_words(titles)
    if not words:
        raise ValueError("the paper titles contained no usable words")

    return YearResult(
        year=year,
        source_url=source_url,
        paper_count=len(titles),
        words=tuple(words),
        top_words=tuple(top_words(words, top_word_count)),
    )


HTML_PREFIX = """\
    <html>
      <head>
        <meta charset="utf-8">
        <title>SIGGRAPH Word Clouds</title>
        <meta name="author" content="Anjul Patney">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
        <link href="https://fonts.googleapis.com/css?family=Source+Sans+Pro" rel="stylesheet">
        <link href="static/main.css" rel="stylesheet" type="text/css">
      </head>
      <body>
"""

HTML_POSTFIX = """\
      <!-- Start of StatCounter Code for Default Guide -->
      <script type="text/javascript">
      var sc_project=10471620; 
      var sc_invisible=1; 
      var sc_security="81ba45aa"; 
      var scJsHost = (("https:" == document.location.protocol) ?
      "https://secure." : "http://www.");
      document.write("<sc"+"ript type='text/javascript' src='" +
      scJsHost+
      "statcounter.com/counter/counter.js'></"+"script>");
      </script>
      <noscript><div class="statcounter"><a title="shopify traffic
      stats" href="http://statcounter.com/shopify/"
      target="_blank"><img class="statcounter"
      src="http://c.statcounter.com/10471620/0/81ba45aa/1/"
      alt="shopify traffic stats"></a></div></noscript>
      <!-- End of StatCounter Code for Default Guide -->
      </body>
    </html>
"""


def render_word_cloud(words: Sequence[tuple[str, int]], total_words: int) -> str:
    """Use the frequency-based sizes and grayscale colors of the original template."""
    levels = (
        (1.0, 250, 250), (0.9, 200, 225), (0.8, 180, 200),
        (0.7, 150, 150), (0.6, 125, 100), (0.5, 100, 50),
        (0.4, 70, 40), (0.3, 50, 40), (0.2, 30, 40),
        (0.1, 20, 40), (0.05, 10, 40),
    )
    rendered: list[str] = []
    for word, count in words:
        frequency = 100.0 * count / total_words
        size, darkness = next(
            ((size, darkness) for threshold, size, darkness in levels if frequency > threshold),
            (5, 40),
        )
        intensity = 255 - darkness
        rendered.append(
            f'<span style="font-size: {size}%; color: rgb({intensity},{intensity},{intensity})">'
            f'{html.escape(word)}</span> ({count}) &nbsp;&nbsp;'
        )
    return "".join(rendered)


def render_page(
    conference: Conference,
    results: Sequence[YearResult],
    failed_years: Sequence[tuple[int, str]],
) -> str:
    """Render refreshed data using the latest checked-in word-cloud template."""
    title = html.escape(conference.title)
    source_name = "CVPR Open Access Page" if conference.parser == "cvpr" else "Ke-Sen Huang's page"
    notes = [
        f'<li>Using data from <a href="{html.escape(conference.source_home, quote=True)}">'
        f'{source_name}</a>. For source of this script, '
        '<a href="https://github.com/ap1/siggraph-wordcloud">click here</a>.</li>',
        f'<li>Words ignored: {html.escape(", ".join(sorted(COMMON_WORDS)))}</li>',
        "<li>If you use this tool, please respect the host's bandwidth limits and only run it a few times, offline.</li>",
        "<li>Feedback: anjul dot patney at gmail dot com</li>",
    ]
    if failed_years:
        years = ", ".join(str(year) for year, _ in failed_years)
        notes.append(f"<li>No usable index was available for {html.escape(years)}; those years were left out.</li>")
    sections = [
        HTML_PREFIX,
        '<table class="ex"><tr><td>',
        f'<br><p class="page_title">{title} Paper Title Word Clouds</p>\n',
        '<p>A very poor attempt to identify trends in graphics/ML research.</p>\n',
        '<strong>Notes</strong><ul>\n',
        "\n".join(notes),
        '\n</ul>\n',
    ]
    for result in results:
        sections.extend([
            f'<p class="topic_header"><a href="{html.escape(result.source_url, quote=True)}">'
            f'{title} {result.year} ({len(result.words)})</a></p>\n',
            '<div class="topic_content">\n',
            render_word_cloud(result.top_words, len(result.words)),
            '\n</div>\n',
        ])
    sections.extend(['</td></tr></table>\n', HTML_POSTFIX])
    return "".join(sections)


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
        ) as temporary:
            temporary.write(content)
            temporary_name = temporary.name
        os.replace(temporary_name, path)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)


def generate_conference(
    conference: Conference,
    output_dir: Path,
    start_year: int | None,
    end_year: int,
    timeout: float,
    delay: float,
    top_word_count: int,
    session: requests.Session,
) -> tuple[list[YearResult], list[tuple[int, str]]]:
    first_year = start_year if start_year is not None else conference.first_year
    if first_year > end_year:
        raise ValueError(f"start year {first_year} is later than end year {end_year}")

    results: list[YearResult] = []
    failures: list[tuple[int, str]] = []
    for year in range(end_year, first_year - 1, -1):
        url = conference.year_url(year)
        print(f"[{conference.slug}] {year}: {url}")
        try:
            result = fetch_year(session, conference, year, timeout, top_word_count)
        except (requests.RequestException, ValueError) as error:
            message = str(error).replace("\n", " ")
            failures.append((year, message))
            print(f"  skipped: {message}")
        else:
            results.append(result)
            print(f"  {result.paper_count:,} papers, {len(result.words):,} useful words")
        if delay and year != first_year:
            time.sleep(delay)

    if not results:
        raise RuntimeError(
            f"No usable {conference.title} pages were found; existing output was left untouched."
        )

    page_path = output_dir / f"{conference.slug}.html"
    word_path = output_dir / f"{conference.slug}_words.txt"
    all_words = [word for result in results for word in result.words]
    word_list = ",".join(word for word, _ in top_words(all_words, WORD_LIST_SIZE))
    atomic_write(page_path, render_page(conference, results, failures))
    atomic_write(word_path, word_list + "\n")
    print(f"  wrote {page_path} and {word_path}")
    return results, failures


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate paper-title trend pages from public conference indexes."
    )
    parser.add_argument(
        "conferences",
        nargs="*",
        choices=tuple(CONFERENCES),
        metavar="CONFERENCE",
        help=f"one or more of: {', '.join(CONFERENCES)} (default: all)",
    )
    parser.add_argument("--start-year", type=int, help="override the conference's first year")
    parser.add_argument(
        "--end-year", type=int, default=date.today().year, help="last year to fetch (default: current year)"
    )
    parser.add_argument("--top-words", type=int, default=DEFAULT_TOP_WORDS)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args(argv)

    if args.top_words < 1:
        parser.error("--top-words must be at least 1")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than 0")
    if args.delay < 0:
        parser.error("--delay cannot be negative")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    selected = args.conferences or list(CONFERENCES)
    session = create_session()
    failed_conferences: list[str] = []
    try:
        for slug in selected:
            try:
                generate_conference(
                    CONFERENCES[slug],
                    args.output_dir,
                    args.start_year,
                    args.end_year,
                    args.timeout,
                    args.delay,
                    args.top_words,
                    session,
                )
            except (RuntimeError, ValueError) as error:
                failed_conferences.append(slug)
                print(f"[{slug}] error: {error}")
    finally:
        session.close()

    if failed_conferences:
        print(f"Failed conferences: {', '.join(failed_conferences)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
