"""Compare original design with native Windows screenshot; diagnostic, not pixel identity certification."""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageChops, ImageStat

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--reference",required=True)
    p.add_argument("--actual",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args()
    with Image.open(args.reference) as a,Image.open(args.actual) as b:
        ref,actual=a.convert("RGB"),b.convert("RGB")
    if ref.size!=(1672,941) or actual.size!=ref.size:
        raise ValueError("reference and actual must both be 1672x941")
    delta=ImageChops.difference(ref,actual)
    report={"dimensions":list(ref.size),"mean_absolute_rgb_difference":round(sum(ImageStat.Stat(delta).mean)/3,4),
            "pixel_identity":delta.getbbox() is None,
            "note":"Reference contains illustrative data; actual contains real fixture/empty states. Pixel difference is diagnostic, not a fidelity pass."}
    out=Path(args.output)
    out.mkdir(parents=True,exist_ok=True)
    side=Image.new("RGB",(ref.width*2,ref.height))
    side.paste(ref,(0,0));side.paste(actual,(ref.width,0))
    side.save(out/"reference-vs-windows.png")
    delta.save(out/"absolute-pixel-difference.png")
    (out/"comparison.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report))

if __name__=="__main__":
    main()
