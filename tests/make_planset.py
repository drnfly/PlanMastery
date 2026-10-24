import pymupdf

doc = pymupdf.open()
p = doc.new_page(width=1728, height=1152)
p.insert_text((80, 120), "SMITH RESIDENCE - CONSTRUCTION DOCUMENTS", fontsize=36)
p.insert_text((80, 200), "SHEET INDEX: A-000 COVER, A-101 FIRST FLOOR PLAN, S-201 FOUNDATION PLAN", fontsize=20)
p.insert_text((1300, 1100), "A-000 COVER SHEET", fontsize=24)

p = doc.new_page(width=1728, height=1152)
p.insert_image(pymupdf.Rect(100, 80, 1500, 1080), filename="/app/tests/sample_floorplan.png")
p.insert_text((1300, 1100), "A-101 FIRST FLOOR PLAN", fontsize=24)

p = doc.new_page(width=1728, height=1152)
p.draw_rect(pymupdf.Rect(300, 200, 1300, 950), width=6)
p.insert_text((650, 180), "40'-0\"", fontsize=22)
p.insert_text((180, 580), "30'-0\"", fontsize=22)
p.insert_text((400, 400), "ICF FOUNDATION WALL 8\" CONCRETE CORE, 11\" OVERALL", fontsize=18)
p.insert_text((400, 440), "#5 VERT @ 16\" O.C., (2) #4 HORIZ EVERY OTHER COURSE", fontsize=18)
p.insert_text((400, 480), "FOOTING 24\" W x 12\" D CONTINUOUS, (3) #4 LONG.", fontsize=18)
p.insert_text((400, 520), "WATERPROOFING: PEEL & STICK MEMBRANE + DRAINAGE BOARD, 4\" PERF DRAIN TILE", fontsize=18)
p.insert_text((1300, 1100), "S-201 FOUNDATION PLAN", fontsize=24)
doc.save("/app/tests/sample_planset.pdf")
print("ok")
