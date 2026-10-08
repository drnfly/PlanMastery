from PIL import Image, ImageDraw, ImageFont

W, H = 1400, 1000
img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)
try:
    f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    fs = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
except Exception:
    f = fs = ImageFont.load_default()
# 1 ft = 25 px; house 40' x 30' at (200,150)
x0, y0, s = 200, 150, 25
def ft(v): return int(v * s)
d.rectangle([x0, y0, x0 + ft(40), y0 + ft(30)], outline="black", width=8)
d.line([x0 + ft(16), y0, x0 + ft(16), y0 + ft(30)], fill="black", width=4)
d.line([x0 + ft(16), y0 + ft(14), x0 + ft(40), y0 + ft(14)], fill="black", width=4)
d.line([x0 + ft(28), y0 + ft(14), x0 + ft(28), y0 + ft(30)], fill="black", width=4)
d.text((x0 + ft(4), y0 + ft(13)), "LIVING ROOM\n16'-0\" x 30'-0\"", fill="black", font=f)
d.text((x0 + ft(23), y0 + ft(6)), "KITCHEN\n24'-0\" x 14'-0\"", fill="black", font=f)
d.text((x0 + ft(18), y0 + ft(21)), "BEDROOM\n12'-0\" x 16'-0\"", fill="black", font=f)
d.text((x0 + ft(30), y0 + ft(21)), "BATH\n12'-0\" x 16'-0\"", fill="black", font=f)
# dims
d.line([x0, y0 - 50, x0 + ft(40), y0 - 50], fill="black", width=2)
d.text((x0 + ft(18), y0 - 80), "40'-0\"", fill="black", font=f)
d.line([x0 - 60, y0, x0 - 60, y0 + ft(30)], fill="black", width=2)
d.text((x0 - 140, y0 + ft(15)), "30'-0\"", fill="black", font=f)
# door
d.rectangle([x0 + ft(6), y0 + ft(30) - 6, x0 + ft(9), y0 + ft(30) + 6], fill="white")
d.text((x0 + ft(6), y0 + ft(30) + 12), "D1 3'-0\" x 6'-8\"", fill="black", font=fs)
d.rectangle([x0 + ft(30), y0 - 6, x0 + ft(35), y0 + 6], fill="white", outline="black")
d.text((x0 + ft(30), y0 + 12), "W1 5'-0\" x 4'-0\"", fill="black", font=fs)
d.text((x0, H - 70), "GROUND FLOOR PLAN   SCALE: 1/4\" = 1'-0\"   EXT WALLS 2x6, INT WALLS 2x4", fill="black", font=f)
img.save("/app/tests/sample_floorplan.png")
print("ok")
