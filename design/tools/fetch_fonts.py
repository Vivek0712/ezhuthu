"""Download the OFL fonts used by the design build into ~/.cache/ezhuthu-design-fonts (or $EZ_FONT_DIR).

Sources are the google/fonts repository (all SIL Open Font License 1.1). See design/brand/FONTS.md.
"""
import os
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
FONTS = {
    "NotoSerifTamil.ttf": "notoseriftamil/NotoSerifTamil%5Bwdth,wght%5D.ttf",
    "NotoSansTamil.ttf": "notosanstamil/NotoSansTamil%5Bwdth,wght%5D.ttf",
    "NotoSansBrahmi-Regular.ttf": "notosansbrahmi/NotoSansBrahmi-Regular.ttf",
    "NotoSansGrantha-Regular.ttf": "notosansgrantha/NotoSansGrantha-Regular.ttf",
    "Fraunces.ttf": "fraunces/Fraunces%5BSOFT,WONK,opsz,wght%5D.ttf",
    "Fraunces-Italic.ttf": "fraunces/Fraunces-Italic%5BSOFT,WONK,opsz,wght%5D.ttf",
    "InstrumentSans.ttf": "instrumentsans/InstrumentSans%5Bwdth,wght%5D.ttf",
}

if __name__ == "__main__":
    out = Path(os.environ.get("EZ_FONT_DIR", Path.home() / ".cache" / "ezhuthu-design-fonts"))
    out.mkdir(parents=True, exist_ok=True)
    for name, rel in FONTS.items():
        dst = out / name
        if not dst.exists():
            urllib.request.urlretrieve(BASE + rel, dst)
        print(dst)
