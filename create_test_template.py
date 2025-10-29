"""
Скрипт для создания тестового шаблона билета.
Запустите: python create_test_template.py
"""

from PIL import Image, ImageDraw, ImageFont

def create_ticket_template():
    """Создает простой шаблон билета для тестирования"""
    
    # Размеры билета
    width = 1200
    height = 600
    
    # Создаем изображение
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Рисуем границы
    border_color = '#2196F3'
    draw.rectangle([(10, 10), (width-10, height-10)], outline=border_color, width=5)
    
    # Заголовок
    draw.rectangle([(10, 10), (width-10, 100)], fill=border_color)
    
    # Пытаемся загрузить шрифт
    try:
        title_font = ImageFont.truetype("Futuralightc (2).otf", 60)
        label_font = ImageFont.truetype("denistina_en (2).ttf", 30)
    except:
        try:
            title_font = ImageFont.truetype("arial.ttf", 60)
            label_font = ImageFont.truetype("arial.ttf", 30)
        except:
            title_font = ImageFont.load_default()
            label_font = ImageFont.load_default()
    
    # Текст заголовка
    draw.text((width/2, 55), "БИЛЕТ НА МЕРОПРИЯТИЕ", 
              fill='white', font=title_font, anchor='mm')
    
    # Метки для полей
    y_offset = 150
    line_height = 70
    
    labels = [
        "ФИО:",
        "Группа:",
        "Студенческий билет:",
        "Тип билета:"
    ]
    
    for i, label in enumerate(labels):
        y = y_offset + (i * line_height)
        draw.text((100, y), label, fill='#333', font=label_font)
    
    # Область для QR-кода
    qr_box = [(850, 250), (1100, 500)]
    draw.rectangle(qr_box, outline='#ccc', width=2)
    draw.text((975, 525), "QR-код", fill='#666', font=label_font, anchor='mm')
    
    # Нижний текст
    draw.text((width/2, height-30), "Предъявите этот билет на входе", 
              fill='#666', font=label_font, anchor='mm')
    
    # Сохраняем
    img.save('ticket_template.png')
    print("✅ Шаблон билета создан: ticket_template.png")
    print("📐 Размер: 1200x600 px")
    print("📍 Позиция QR-кода: (900, 300)")
    print("\n💡 Вы можете заменить этот файл своим дизайном!")

if __name__ == '__main__':
    create_ticket_template()

