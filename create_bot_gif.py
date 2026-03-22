#!/usr/bin/env python3
"""
Скрипт для создания анимированных GIF-изображений для Family Finance Bot.
Создаёт красивую анимацию с финансовой тематикой в трёх разрешениях.
"""

import math
from PIL import Image, ImageDraw, ImageFont
import os

# Цветовая схема - современный финансовый стиль
COLORS = {
    'bg_dark': '#0D1B2A',       # Тёмно-синий фон
    'bg_gradient': '#1B263B',   # Градиент фона
    'primary': '#00D9A5',       # Бирюзовый/мятный (главный акцент)
    'secondary': '#7B61FF',     # Фиолетовый
    'accent': '#FFB800',        # Золотой (для монет)
    'accent2': '#FF6B6B',       # Коралловый
    'text': '#E0E7FF',          # Светлый текст
    'white': '#FFFFFF',
    'chart_green': '#00E676',   # Зелёный для графиков
    'chart_red': '#FF5252',     # Красный для графиков
}

def hex_to_rgb(hex_color):
    """Конвертация HEX в RGB"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def interpolate_color(color1, color2, factor):
    """Интерполяция между двумя цветами"""
    r1, g1, b1 = hex_to_rgb(color1)
    r2, g2, b2 = hex_to_rgb(color2)
    r = int(r1 + (r2 - r1) * factor)
    g = int(g1 + (g2 - g1) * factor)
    b = int(b1 + (b2 - b1) * factor)
    return (r, g, b)

def draw_gradient_background(draw, width, height):
    """Рисует градиентный фон"""
    for y in range(height):
        factor = y / height
        color = interpolate_color(COLORS['bg_dark'], COLORS['bg_gradient'], factor)
        draw.line([(0, y), (width, y)], fill=color)

def draw_coin(draw, x, y, radius, rotation, glow=False):
    """Рисует анимированную монету с 3D эффектом"""
    # Сжатие по горизонтали для 3D эффекта вращения
    squeeze = abs(math.cos(rotation))
    
    if squeeze < 0.1:
        squeeze = 0.1
    
    # Свечение
    if glow:
        for i in range(3):
            glow_radius = radius + (3 - i) * (radius // 5)
            draw.ellipse(
                [x - glow_radius * squeeze, y - glow_radius,
                 x + glow_radius * squeeze, y + glow_radius],
                fill=(*hex_to_rgb(COLORS['accent']), 20 + i * 10)
            )
    
    # Основа монеты
    gold_main = hex_to_rgb(COLORS['accent'])
    gold_dark = tuple(max(0, c - 40) for c in gold_main)
    gold_light = tuple(min(255, c + 40) for c in gold_main)
    
    # Основной эллипс
    draw.ellipse(
        [x - radius * squeeze, y - radius,
         x + radius * squeeze, y + radius],
        fill=gold_main
    )
    
    # Блик
    highlight_radius = radius * 0.7
    draw.ellipse(
        [x - highlight_radius * squeeze * 0.8, y - highlight_radius * 0.9,
         x + highlight_radius * squeeze * 0.3, y - radius * 0.2],
        fill=gold_light
    )
    
    # Символ валюты (₽)
    if squeeze > 0.5:
        # Простой символ рубля через линии
        cx, cy = x, y
        line_width = max(1, int(radius / 8))
        symbol_color = gold_dark
        
        # Вертикальная линия
        draw.line([(cx - radius * 0.2 * squeeze, cy - radius * 0.4),
                   (cx - radius * 0.2 * squeeze, cy + radius * 0.4)],
                  fill=symbol_color, width=line_width)
        # Дуга (упрощённо - полукруг)
        draw.arc(
            [cx - radius * 0.3 * squeeze, cy - radius * 0.4,
             cx + radius * 0.3 * squeeze, cy + radius * 0.1],
            start=-90, end=90, fill=symbol_color, width=line_width
        )
        # Горизонтальная черта
        draw.line([(cx - radius * 0.35 * squeeze, cy + radius * 0.15),
                   (cx + radius * 0.1 * squeeze, cy + radius * 0.15)],
                  fill=symbol_color, width=line_width)

def draw_chart(draw, x, y, width, height, frame, total_frames):
    """Рисует анимированный график"""
    # Фон графика
    chart_bg = (*hex_to_rgb(COLORS['bg_dark']), 150)
    draw.rounded_rectangle(
        [x, y, x + width, y + height],
        radius=width // 15,
        fill=chart_bg
    )
    
    # Сетка
    grid_color = (*hex_to_rgb(COLORS['text']), 30)
    for i in range(1, 4):
        gy = y + (height * i // 4)
        draw.line([(x + 5, gy), (x + width - 5, gy)], fill=grid_color, width=1)
    
    # Данные графика (волнистая линия)
    points = []
    num_points = 8
    progress = frame / total_frames
    
    for i in range(num_points + 1):
        px = x + 10 + (width - 20) * i / num_points
        # Анимированная синусоида + тренд вверх
        wave = math.sin((i / num_points + progress) * 2 * math.pi) * 0.2
        trend = (i / num_points) * 0.4
        value = 0.3 + trend + wave
        py = y + height - (height * 0.1) - (height * 0.8 * value)
        points.append((px, py))
    
    # Заливка под графиком
    fill_points = points.copy()
    fill_points.append((x + width - 10, y + height - 5))
    fill_points.append((x + 10, y + height - 5))
    
    # Градиентная заливка (упрощённая)
    gradient_color = (*hex_to_rgb(COLORS['chart_green']), 50)
    draw.polygon(fill_points, fill=gradient_color)
    
    # Линия графика
    if len(points) > 1:
        draw.line(points, fill=hex_to_rgb(COLORS['chart_green']), width=max(2, width // 40))
    
    # Точки на графике
    for px, py in points[::2]:
        dot_radius = max(2, width // 50)
        draw.ellipse(
            [px - dot_radius, py - dot_radius, px + dot_radius, py + dot_radius],
            fill=hex_to_rgb(COLORS['white'])
        )

def draw_family_icon(draw, x, y, size, pulse):
    """Рисует иконку семьи (3 фигурки)"""
    # Пульсация размера
    scale = 1 + pulse * 0.1
    
    icon_color = hex_to_rgb(COLORS['primary'])
    head_radius = int(size * 0.12 * scale)
    body_height = int(size * 0.25 * scale)
    
    # Три фигурки
    positions = [
        (x - size * 0.25, 0.9),   # Левая (меньше)
        (x, 1.0),                  # Центральная (больше)
        (x + size * 0.25, 0.85),  # Правая (меньше)
    ]
    
    for px, size_factor in positions:
        # Голова
        hr = int(head_radius * size_factor)
        draw.ellipse(
            [px - hr, y - body_height - hr * 2,
             px + hr, y - body_height],
            fill=icon_color
        )
        # Тело (треугольник/трапеция)
        bh = int(body_height * size_factor)
        bw = int(size * 0.12 * size_factor * scale)
        draw.polygon([
            (px, y - bh),
            (px - bw, y),
            (px + bw, y)
        ], fill=icon_color)

def draw_wallet_icon(draw, x, y, size, open_factor):
    """Рисует иконку кошелька"""
    wallet_color = hex_to_rgb(COLORS['secondary'])
    wallet_dark = tuple(max(0, c - 30) for c in wallet_color)
    
    # Основа кошелька
    w = size * 0.6
    h = size * 0.4
    
    # Открытие кошелька
    flap_offset = open_factor * h * 0.3
    
    draw.rounded_rectangle(
        [x - w/2, y - h/2 + flap_offset, x + w/2, y + h/2],
        radius=size // 15,
        fill=wallet_color
    )
    
    # Крышка кошелька
    draw.rounded_rectangle(
        [x - w/2, y - h/2 - flap_offset, x + w/2, y - h/2 + h * 0.3],
        radius=size // 15,
        fill=wallet_dark
    )
    
    # Застёжка
    clasp_size = size * 0.08
    draw.ellipse(
        [x - clasp_size, y - h/2 + h * 0.25 - clasp_size,
         x + clasp_size, y - h/2 + h * 0.25 + clasp_size],
        fill=hex_to_rgb(COLORS['accent'])
    )

def draw_text_logo(draw, x, y, width, height, alpha):
    """Рисует текстовый логотип"""
    # Основной текст
    text_main = "💰 Family Finance"
    text_sub = "Bot"
    
    # Размеры шрифтов (относительные)
    main_size = int(height * 0.12)
    sub_size = int(height * 0.08)
    
    try:
        # Пробуем системные шрифты
        font_main = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", main_size)
        font_sub = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", sub_size)
    except Exception:
        try:
            font_main = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", main_size)
            font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", sub_size)
        except Exception:
            font_main = ImageFont.load_default()
            font_sub = ImageFont.load_default()
    
    # Цвета текста с альфа-каналом
    text_color = (*hex_to_rgb(COLORS['text']), int(255 * alpha))
    accent_color = (*hex_to_rgb(COLORS['primary']), int(255 * alpha))
    
    # Основной текст
    bbox = draw.textbbox((0, 0), text_main, font=font_main)
    text_width = bbox[2] - bbox[0]
    draw.text((x - text_width // 2, y), text_main, font=font_main, fill=text_color)
    
    # Подзаголовок
    bbox_sub = draw.textbbox((0, 0), text_sub, font=font_sub)
    sub_width = bbox_sub[2] - bbox_sub[0]
    draw.text((x - sub_width // 2, y + main_size + 5), text_sub, font=font_sub, fill=accent_color)

def draw_particles(draw, width, height, frame, total_frames):
    """Рисует летающие частицы (блики, звёздочки)"""
    import random
    random.seed(42)  # Фиксированный seed для воспроизводимости
    
    num_particles = 15
    for i in range(num_particles):
        # Базовая позиция
        base_x = random.random() * width
        base_y = random.random() * height
        
        # Анимация позиции
        progress = (frame / total_frames + i / num_particles) % 1.0
        px = base_x + math.sin(progress * 2 * math.pi + i) * 20
        py = base_y - progress * height * 0.3  # Движение вверх
        py = py % height
        
        # Размер и прозрачность
        size = random.randint(1, 3)
        alpha = int(100 + 100 * math.sin(progress * 2 * math.pi))
        
        particle_color = (*hex_to_rgb(COLORS['primary']), alpha)
        draw.ellipse(
            [px - size, py - size, px + size, py + size],
            fill=particle_color
        )

def create_frame(width, height, frame_num, total_frames):
    """Создаёт один кадр анимации"""
    # RGBA для поддержки прозрачности
    img = Image.new('RGBA', (width, height), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img, 'RGBA')
    
    # Прогресс анимации (0.0 - 1.0)
    progress = frame_num / total_frames
    
    # Фон с градиентом
    draw_gradient_background(draw, width, height)
    
    # Частицы на заднем плане
    draw_particles(draw, width, height, frame_num, total_frames)
    
    # Центральные координаты
    cx, cy = width // 2, height // 2
    
    # Монеты (вращающиеся)
    coin_radius = int(min(width, height) * 0.08)
    
    # Левая монета
    coin1_x = cx - width * 0.32
    coin1_y = cy + math.sin(progress * 2 * math.pi) * 10
    draw_coin(draw, coin1_x, coin1_y, coin_radius, progress * 2 * math.pi, glow=True)
    
    # Правая монета (с задержкой)
    coin2_x = cx + width * 0.32
    coin2_y = cy + math.sin((progress + 0.5) * 2 * math.pi) * 10
    draw_coin(draw, coin2_x, coin2_y, coin_radius, (progress + 0.5) * 2 * math.pi, glow=True)
    
    # Маленькие монетки
    small_coin_radius = int(coin_radius * 0.5)
    for i, (offset_x, offset_y, phase) in enumerate([
        (-0.2, -0.25, 0.2),
        (0.2, -0.28, 0.4),
        (-0.25, 0.2, 0.6),
        (0.25, 0.22, 0.8),
    ]):
        scx = cx + width * offset_x
        scy = cy + height * offset_y + math.sin((progress + phase) * 2 * math.pi) * 5
        draw_coin(draw, scx, scy, small_coin_radius, (progress + phase) * 2 * math.pi)
    
    # График в центре
    chart_width = int(width * 0.35)
    chart_height = int(height * 0.35)
    chart_x = cx - chart_width // 2
    chart_y = cy - chart_height // 2 + int(height * 0.05)
    draw_chart(draw, chart_x, chart_y, chart_width, chart_height, frame_num, total_frames)
    
    # Иконка семьи над графиком
    family_y = chart_y - int(height * 0.05)
    pulse = math.sin(progress * 4 * math.pi) * 0.5 + 0.5
    draw_family_icon(draw, cx, family_y, int(width * 0.15), pulse)
    
    # Текст логотипа внизу
    text_y = cy + int(height * 0.28)
    text_alpha = 0.7 + 0.3 * math.sin(progress * 2 * math.pi)
    draw_text_logo(draw, cx, text_y, width, height, text_alpha)
    
    # Конвертируем в RGB для GIF
    rgb_img = Image.new('RGB', (width, height), hex_to_rgb(COLORS['bg_dark']))
    rgb_img.paste(img, mask=img.split()[3])
    
    return rgb_img

def create_animated_gif(width, height, filename, num_frames=30, duration=100):
    """Создаёт анимированный GIF"""
    print(f"Создание {filename} ({width}x{height})...")
    
    frames = []
    for i in range(num_frames):
        print(f"  Кадр {i+1}/{num_frames}", end='\r')
        frame = create_frame(width, height, i, num_frames)
        frames.append(frame)
    
    print("  Сохранение...")
    
    # Сохраняем GIF
    frames[0].save(
        filename,
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,  # Бесконечный цикл
        optimize=True
    )
    
    file_size = os.path.getsize(filename) / 1024
    print(f"  ✅ Готово: {filename} ({file_size:.1f} KB)")

def main():
    """Главная функция"""
    print("=" * 50)
    print("🎬 Создание GIF-анимаций для Family Finance Bot")
    print("=" * 50)
    
    # Создаём папку для изображений
    output_dir = "assets"
    os.makedirs(output_dir, exist_ok=True)
    
    # Разрешения (16:9 aspect ratio)
    resolutions = [
        (320, 180, "bot_animation_320x180.gif"),
        (640, 360, "bot_animation_640x360.gif"),
        (960, 540, "bot_animation_960x540.gif"),
    ]
    
    for width, height, filename in resolutions:
        filepath = os.path.join(output_dir, filename)
        create_animated_gif(width, height, filepath, num_frames=24, duration=80)
    
    print("\n" + "=" * 50)
    print("✨ Все GIF-файлы успешно созданы!")
    print(f"📁 Расположение: {os.path.abspath(output_dir)}/")
    print("=" * 50)

if __name__ == "__main__":
    main()







