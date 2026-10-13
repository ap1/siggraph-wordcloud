# Conference paper-title trends

A small static-site generator that visualizes recurring words in paper titles from SIGGRAPH, SIGGRAPH Asia, CVPR, High-Performance Graphics, and the Eurographics Symposium on Rendering.

Published pages: [SIGGRAPH](https://ap1.github.io/siggraph-wordcloud/sig.html), [SIGGRAPH Asia](https://ap1.github.io/siggraph-wordcloud/siga.html), and [CVPR](https://ap1.github.io/siggraph-wordcloud/cvpr.html).

## Generate pages

Python 3.10+ and `requests` are required.

```powershell
python top5words.py sig
python top5words.py cvpr
python top5words.py sig siga cvpr
```

With no conference arguments, the script generates every configured page. It writes each HTML page and its companion `_words.txt` file atomically, so a failed fetch cannot truncate a previously generated result.

Useful options:

```powershell
python top5words.py sig --start-year 2020 --end-year 2025 --delay 0
python top5words.py --help
```

SIGGRAPH-family data comes from [Ke-Sen Huang's paper indexes](https://kesen.realtimerendering.com/); CVPR data comes from [CVF Open Access](https://openaccess.thecvf.com/). Please keep the default delay when regenerating the full history to respect those services' bandwidth.
