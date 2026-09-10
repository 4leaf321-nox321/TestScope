"""PDF 특정 쪽을 PNG 로 렌더링한다. 표 열이 흐트러진 사양표를 눈으로 확인하기 위한 것.

사용: render_pages.py <pdf 상대경로> <쪽번호,쪽번호...> [배율]
      쪽번호는 추출 텍스트의 '===== page N =====' 과 같은 1-기반 번호.
"""
import os
import sys

import fitz

PDFDIR = r"F:\data\0_Program\68_TestScope\source\pdf"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pages")

rel = sys.argv[1]
pages = [int(x) for x in sys.argv[2].split(",")]
zoom = float(sys.argv[3]) if len(sys.argv) > 3 else 2.2

os.makedirs(OUT, exist_ok=True)
doc = fitz.open(os.path.join(PDFDIR, rel))
stem = os.path.splitext(os.path.basename(rel))[0]
for p in pages:
    page = doc[p - 1]
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    path = os.path.join(OUT, f"{stem}-p{p}.png")
    pix.save(path)
    print(path, f"{pix.width}x{pix.height}")
doc.close()
