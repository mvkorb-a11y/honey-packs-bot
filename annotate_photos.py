from PIL import Image, ImageDraw, ImageFont, ImageOps
import os

def process_and_annotate():
    base_dir = "/Users/mihhailkorb/.gemini/antigravity/scratch/honey_packs"
    
    # 1. IMG_3635.jpg (The sheep logo bags - Toortatrajahu)
    img35_path = os.path.join(base_dir, "IMG_3635.jpg")
    img35 = Image.open(img35_path)
    img35 = ImageOps.exif_transpose(img35)
    
    w, h = img35.size
    draw35 = ImageDraw.Draw(img35)
    
    def draw_thick_box(draw_obj, box, color, label, width=14):
        for i in range(width):
            b = [box[0]-i, box[1]-i, box[2]+i, box[3]+i]
            draw_obj.rectangle(b, outline=color)
        banner_h = 80
        draw_obj.rectangle([box[0], max(0, box[1]-banner_h), min(w, box[0]+1100), box[1]], fill=color)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 44)
        except:
            font = ImageFont.load_default()
        draw_obj.text((box[0]+15, max(0, box[1]-banner_h)+15), label, fill="black", font=font)

    # Box 1: Paper bag Mahe toor-tatrajahu (Sheep logo, 1kg)
    box_tatrahaju_bag = [int(w * 0.14), int(h * 0.16), int(w * 0.43), int(h * 0.52)]
    # Box 2: Price tag 4.79 € for 1kg
    box_tatrajahu_price = [int(w * 0.14), int(h * 0.54), int(w * 0.32), int(h * 0.62)]
    # Box 3: Black pouch Toor-tatra kama
    box_kama_pouch = [int(w * 0.67), int(h * 0.20), int(w * 0.93), int(h * 0.52)]

    draw_thick_box(draw35, box_tatrahaju_bag, "#00FF00", "МУКА ЗЕЛЕНОЙ ГРЕЧКИ 1 кг (Mahe toor-tatrajahu)")
    draw_thick_box(draw35, box_tatrajahu_price, "#00FF00", "ЦЕННИК: 4.79 € за 1 кг")
    draw_thick_box(draw35, box_kama_pouch, "#FFFF00", "ТОЛОКНО ЗЕЛЕНОЙ ГРЕЧКИ (Toor-tatra kama 2.89 €)")
    
    out35_path = os.path.join(base_dir, "annotated_IMG_3635.jpg")
    img35.save(out35_path, quality=92)

    # 2. IMG_3632.jpg (Shelf with Veski Mati Riisijahu, Linaseemned, Kanepijahu)
    img32_path = os.path.join(base_dir, "IMG_3632.jpg")
    img32 = Image.open(img32_path)
    img32 = ImageOps.exif_transpose(img32)
    w32, h32 = img32.size
    draw32 = ImageDraw.Draw(img32)
    
    # Riisijahu (Veski Mati - 3rd shelf down, right blue bags)
    box_riis = [int(w32 * 0.78), int(h32 * 0.63), int(w32 * 0.92), int(h32 * 0.68)]
    # Linaseemnejahu (Just Nature - 2nd shelf down)
    box_lina = [int(w32 * 0.72), int(h32 * 0.34), int(w32 * 0.83), int(h32 * 0.41)]
    # Kanepijahu (Tammejuure - top shelf)
    box_kanep = [int(w32 * 0.88), int(h32 * 0.16), int(w32 * 0.98), int(h32 * 0.25)]

    draw_thick_box(draw32, box_riis, "#00FFFF", "РИСОВАЯ МУКА 500g (Veski Mati Riisijahu - 1.82 €)")
    draw_thick_box(draw32, box_lina, "#FF00FF", "ЛЬНЯНАЯ МУКА 300g (Just Nature - 2.23 €)")
    draw_thick_box(draw32, box_kanep, "#00FF00", "КОНОПЛЯНАЯ МУКА 500g (Tammejuure - 5.58 €)")
    
    out32_path = os.path.join(base_dir, "annotated_IMG_3632.jpg")
    img32.save(out32_path, quality=92)

    print("Refined annotations created successfully!")

if __name__ == "__main__":
    process_and_annotate()
