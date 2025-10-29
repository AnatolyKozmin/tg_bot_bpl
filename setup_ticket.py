"""
🎨 Интерактивный конфигуратор билетов
Быстрая настройка дизайна билета с визуальным контролем.

Установка:
    pip install pillow qrcode[pil]

Использование:
    python setup_ticket.py

Результат:
    - Создаёт test_ticket_output.png с тестовым билетом
    - Показывает вспомогательные линии для точной настройки
    - Автоматически подхватывает изменения из ticket_config_local.py
"""

from PIL import Image, ImageDraw, ImageFont
import qrcode
import os
import sys
import shutil

# =============================================================================
# НАСТРОЙКИ СКРИПТА
# =============================================================================

TEMPLATE_PATH = "ticket_template.png"  # Ваш шаблон
OUTPUT_PATH = "test_ticket_output.png"  # Результат

# Тестовые данные
TEST_TELEGRAM_ID = "922109605"
TEST_FIO = "Иванов Иван Петрович"

# Визуальные подсказки
SHOW_DEBUG_LINES = True  # Красные/синие/зелёные линии через центры
SHOW_COORDINATES = True  # Подписи с координатами

# =============================================================================
# ЗАГРУЗКА КОНФИГУРАЦИИ (БЕЗ КЕШИРОВАНИЯ!)
# =============================================================================

def clear_cache():
    """Убирает __pycache__ для чистой загрузки"""
    if os.path.exists("__pycache__"):
        try:
            shutil.rmtree("__pycache__", ignore_errors=True)
        except:
            pass

def load_fresh_config():
    """Читает ticket_config_local.py напрямую, БЕЗ import (без кеша!)"""
    config_file = "ticket_config_local.py"
    
    if not os.path.exists(config_file):
        print(f"❌ Файл {config_file} не найден!")
        print("💡 Создайте его на основе ticket_config.py")
        sys.exit(1)
    
    # Читаем и выполняем код напрямую
    with open(config_file, 'r', encoding='utf-8') as f:
        config_code = f.read()
    
    namespace = {}
    exec(config_code, namespace)
    
    return namespace

# Загружаем конфиг
clear_cache()
cfg = load_fresh_config()

FONT_PATH = cfg['FONT_PATH']
FONT_PATH_FALLBACK = cfg.get('FONT_PATH_FALLBACK')
FONT_SIZES = cfg['FONT_SIZES']
TEXT_POSITIONS = cfg['TEXT_POSITIONS']
TEXT_COLORS = cfg['TEXT_COLORS']
QR_CONFIG = cfg['QR_CONFIG']
QR_DATA_FORMAT = cfg['QR_DATA_FORMAT']

# =============================================================================
# ГЕНЕРАЦИЯ БИЛЕТА
# =============================================================================

def create_qr_code(telegram_id):
    """Создаёт QR-код"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=QR_CONFIG.get('box_size', 10),
        border=QR_CONFIG.get('border', 2),
    )
    
    qr_data = QR_DATA_FORMAT.format(telegram_id=telegram_id)
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    return qr.make_image(fill_color="black", back_color="white")

def extract_name(fio):
    """Извлекает Фамилию и Имя из ФИО"""
    parts = fio.strip().split()
    if len(parts) >= 2:
        return f"{parts[0]} {parts[1]}"
    elif len(parts) == 1:
        return parts[0]
    else:
        return "Участник"

def load_font(font_path, size, fallback_path=None):
    """Загружает шрифт с fallback"""
    try:
        return ImageFont.truetype(font_path, size)
    except Exception as e:
        print(f"   ⚠️  Не загружен {font_path}: {e}")
        if fallback_path:
            try:
                return ImageFont.truetype(fallback_path, size)
            except:
                pass
        return ImageFont.load_default()

def draw_debug_helpers(draw, template_size):
    """Рисует вспомогательные линии и метки"""
    
    # Центры элементов
    qr_center = TEXT_POSITIONS['qr_code']
    id_center = TEXT_POSITIONS['telegram_id']
    name_center = TEXT_POSITIONS['name']
    
    # Вертикальная линия через центр QR
    draw.line(
        [(qr_center[0], 0), (qr_center[0], template_size[1])],
        fill='red', width=2
    )
    
    # Горизонтальные линии
    draw.line(
        [(0, qr_center[1]), (template_size[0], qr_center[1])],
        fill='red', width=1
    )
    draw.line(
        [(0, id_center[1]), (template_size[0], id_center[1])],
        fill='blue', width=2
    )
    draw.line(
        [(0, name_center[1]), (template_size[0], name_center[1])],
        fill='green', width=2
    )
    
    # Крестики в центрах
    for pos, color in [(qr_center, 'red'), (id_center, 'blue'), (name_center, 'green')]:
        draw.line([(pos[0]-15, pos[1]), (pos[0]+15, pos[1])], fill=color, width=3)
        draw.line([(pos[0], pos[1]-15), (pos[0], pos[1]+15)], fill=color, width=3)
    
    # Подписи координат (если включено)
    if SHOW_COORDINATES:
        coord_font = ImageFont.load_default()
        
        labels = [
            (qr_center, f"QR ({qr_center[0]}, {qr_center[1]})", 'red', -30),
            (id_center, f"ID ({id_center[0]}, {id_center[1]})", 'blue', -30),
            (name_center, f"NAME ({name_center[0]}, {name_center[1]})", 'green', -30),
        ]
        
        for pos, text, color, offset_y in labels:
            draw.text((pos[0] + 20, pos[1] + offset_y), text, fill=color, font=coord_font)

def generate_ticket():
    """Генерирует билет с текущими настройками"""
    
    print("\n" + "="*70)
    print("🎫 ГЕНЕРАЦИЯ ТЕСТОВОГО БИЛЕТА")
    print("="*70)
    
    # 1. QR-код
    print("\n1️⃣  Создание QR-кода...")
    qr_img = create_qr_code(TEST_TELEGRAM_ID)
    print(f"   ✅ Данные: {TEST_TELEGRAM_ID}")
    print(f"   ✅ Размер: {QR_CONFIG['size'][0]}x{QR_CONFIG['size'][1]}px")
    
    # 2. Имя
    print("\n2️⃣  Обработка имени...")
    name_text = extract_name(TEST_FIO)
    print(f"   ✅ ФИО: {TEST_FIO}")
    print(f"   ✅ На билете: {name_text}")
    
    # 3. Шаблон
    print("\n3️⃣  Загрузка шаблона...")
    if not os.path.exists(TEMPLATE_PATH):
        print(f"   ⚠️  Шаблон не найден: {TEMPLATE_PATH}")
        print("   📝 Создаём белый холст 1500x2000px...")
        template = Image.new('RGB', (1500, 2000), color='white')
    else:
        template = Image.open(TEMPLATE_PATH).convert('RGB')
        print(f"   ✅ Загружен: {template.size[0]}x{template.size[1]}px")
    
    draw = ImageDraw.Draw(template)
    
    # 4. Шрифты
    print("\n4️⃣  Загрузка шрифтов...")
    font_name = load_font(FONT_PATH, FONT_SIZES['name'], FONT_PATH_FALLBACK)
    font_id = load_font(FONT_PATH, FONT_SIZES['telegram_id'], FONT_PATH_FALLBACK)
    print(f"   ✅ Размер шрифта имени: {FONT_SIZES['name']}px")
    print(f"   ✅ Размер шрифта ID: {FONT_SIZES['telegram_id']}px")
    
    # 5. Размещение QR
    print("\n5️⃣  Размещение QR-кода...")
    qr_img_resized = qr_img.resize(QR_CONFIG['size'])
    qr_center = TEXT_POSITIONS['qr_code']
    qr_x = qr_center[0] - QR_CONFIG['size'][0] // 2
    qr_y = qr_center[1] - QR_CONFIG['size'][1] // 2
    template.paste(qr_img_resized, (qr_x, qr_y))
    print(f"   ✅ Центр: ({qr_center[0]}, {qr_center[1]})")
    print(f"   ✅ Верхний левый угол: ({qr_x}, {qr_y})")
    
    # 6. Telegram ID
    print("\n6️⃣  Размещение Telegram ID...")
    id_text = TEST_TELEGRAM_ID  # Только цифры, без "ID:"
    
    # Вычисляем размер текста
    try:
        bbox = draw.textbbox((0, 0), id_text, font=font_id)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    except:
        text_width, text_height = draw.textsize(id_text, font=font_id)
    
    id_x = TEXT_POSITIONS['telegram_id'][0] - text_width // 2
    id_y = TEXT_POSITIONS['telegram_id'][1] - text_height // 2
    
    draw.text(
        (id_x, id_y),
        id_text,
        fill=TEXT_COLORS.get('telegram_id', '#555555'),
        font=font_id
    )
    print(f"   ✅ Центр: {TEXT_POSITIONS['telegram_id']}")
    print(f"   ✅ Размер текста: {text_width}x{text_height}px")
    print(f"   ✅ Цвет: {TEXT_COLORS.get('telegram_id')}")
    
    # 7. Имя
    print("\n7️⃣  Размещение имени...")
    try:
        bbox = draw.textbbox((0, 0), name_text, font=font_name)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    except:
        text_width, text_height = draw.textsize(name_text, font=font_name)
    
    name_x = TEXT_POSITIONS['name'][0] - text_width // 2
    name_y = TEXT_POSITIONS['name'][1] - text_height // 2
    
    draw.text(
        (name_x, name_y),
        name_text,
        fill=TEXT_COLORS.get('name', 'white'),
        font=font_name
    )
    print(f"   ✅ Центр: {TEXT_POSITIONS['name']}")
    print(f"   ✅ Размер текста: {text_width}x{text_height}px")
    print(f"   ✅ Цвет: {TEXT_COLORS.get('name')}")
    
    # 8. Вспомогательные линии
    if SHOW_DEBUG_LINES:
        print("\n8️⃣  Добавление вспомогательных линий...")
        draw_debug_helpers(draw, template.size)
        print("   🔴 Красная - центр QR-кода")
        print("   🔵 Синяя - центр Telegram ID")
        print("   🟢 Зелёная - центр Имени")
    
    # 9. Сохранение
    print(f"\n9️⃣  Сохранение результата...")
    template.save(OUTPUT_PATH, 'PNG')
    print(f"   ✅ Файл: {OUTPUT_PATH}")
    
    print("\n" + "="*70)
    print("✅ ГОТОВО!")
    print("="*70)
    
    return OUTPUT_PATH

# =============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# =============================================================================

def main():
    print("\n🎨 КОНФИГУРАТОР БИЛЕТОВ")
    print("="*70)
    print("📂 Файлы:")
    print(f"   Конфиг: ticket_config_local.py")
    print(f"   Шаблон: {TEMPLATE_PATH}")
    print(f"   Результат: {OUTPUT_PATH}")
    
    # Показываем текущие настройки
    print("\n📋 Текущие настройки:")
    print(f"   QR-код: {QR_CONFIG['size']} @ ({TEXT_POSITIONS['qr_code']})")
    print(f"   Telegram ID: размер {FONT_SIZES['telegram_id']}px @ ({TEXT_POSITIONS['telegram_id']})")
    print(f"   Имя: размер {FONT_SIZES['name']}px @ ({TEXT_POSITIONS['name']})")
    
    # Генерируем
    try:
        output = generate_ticket()
        
        print("\n💡 Что делать дальше:")
        print("   1. Откройте test_ticket_output.png")
        print("   2. Если нужно - измените координаты в ticket_config_local.py:")
        print("      TEXT_POSITIONS = {")
        print(f"          'qr_code': {TEXT_POSITIONS['qr_code']},")
        print(f"          'telegram_id': {TEXT_POSITIONS['telegram_id']},")
        print(f"          'name': {TEXT_POSITIONS['name']},")
        print("      }")
        print("   3. Запустите снова: python setup_ticket.py")
        print("   4. Когда довольны - скопируйте настройки в ticket_config.py")
        print("\n" + "="*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

