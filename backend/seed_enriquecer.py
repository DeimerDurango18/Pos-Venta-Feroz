"""Enriquecimiento idempotente de datos demo de la empresa actual (id=empresa principal).

Cubre los 6 modelos de negocio en un solo demo: restaurante, bar, minimarket,
ferretería, distribuidora/mayorista y general. No toca datos existentes (solo
agrega categorías, productos y salones que no existan ya).

Uso:  docker exec pos_backend python seed_enriquecer.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import SessionLocal
from app.models import Categoria, Mesa, Producto, Salon

# nombre_categoria -> [(nombre_producto, precio_venta, costo, impuesto_pct)]
CATALOGO = {
    "Desayunos": [
        ("Huevos al gusto", 6000, 3500, 0),
        ("Arepa con queso", 4500, 2000, 0),
        ("Caldo de costilla", 9000, 4500, 0),
        ("Tamal tolimense", 7500, 3800, 0),
        ("Chocolate con pan", 3500, 1500, 0),
    ],
    "Platos Ejecutivos": [
        ("Bandeja paisa", 24000, 12000, 0),
        ("Ajiaco santafereño", 18000, 9000, 0),
        ("Sancocho de gallina", 17000, 8500, 0),
        ("Pechuga a la plancha", 21000, 11000, 0),
        ("Filete de pescado", 22000, 12000, 0),
        ("Lomo de cerdo BBQ", 23000, 12500, 0),
    ],
    "Acompañamientos": [
        ("Arroz blanco", 3500, 1300, 0),
        ("Patacones", 4000, 1500, 0),
        ("Ens. de la casa", 4500, 1800, 0),
        ("Frijoles rojos", 5000, 2200, 0),
        ("Yuca frita", 3800, 1400, 0),
    ],
    "Postres": [
        ("Torta tres leches", 9000, 4500, 0),
        ("Flan de coco", 8000, 3800, 0),
        ("Brownie con helado", 11000, 5000, 0),
        ("Fresas con crema", 8500, 4200, 0),
    ],
    "Licores & Bar": [
        ("Whisky Johnnie Red 750ml", 95000, 65000, 19),
        ("Ron Medellín Añejo 750ml", 68000, 47000, 19),
        ("Vodka Absolut 750ml", 92000, 64000, 19),
        ("Gin Londer 750ml", 120000, 85000, 19),
        ("Aguardiente Antioqueno 375ml", 34000, 23000, 19),
        ("Tequila 750ml", 105000, 72000, 19),
    ],
    "Cervezas": [
        ("Poker lata 330ml", 3200, 2100, 19),
        ("Aguila lata 330ml", 3200, 2100, 19),
        ("Club Colombia 330ml", 4000, 2600, 19),
        ("Corona 355ml", 5000, 3300, 19),
        ("Heineken 330ml", 5500, 3600, 19),
        ("Colombiana Roja 350ml", 2500, 1500, 19),
    ],
    "Snacks": [
        ("Papas Macho 45g", 2000, 1200, 19),
        ("Choclitos 40g", 1500, 800, 19),
        ("Detodito 45g", 2000, 1200, 19),
        ("Maíz Tostado 100g", 1800, 900, 19),
        ("Maní Salado 100g", 2200, 1200, 19),
        ("Almendras 50g", 4500, 2800, 19),
    ],
    "Herramientas": [
        ("Martillo 16 oz", 35000, 21000, 19),
        ("Serrucho 20 pulgadas", 28000, 16500, 19),
        ("Taladro 1/2 pulgada", 220000, 150000, 19),
        ("Atornillador juego 12p", 32000, 19000, 19),
        ("Llave expansiva 10 pulg", 27000, 16000, 19),
        ("Cinta métrica 5m", 15000, 8500, 19),
    ],
    "Materiales de Construcción": [
        ("Cemento Gris 50kg", 32000, 26000, 19),
        ("Ladrillo tolete (und)", 1200, 800, 19),
        ("Varilla 3/8 x 6m", 24500, 19000, 19),
        ("Block 40 (und)", 2500, 1700, 19),
        ("Arena lavada bulto", 18000, 12000, 19),
        ("Tubo PVC 1/2 x 3m", 8500, 5200, 19),
    ],
    "Pinturas & Acabados": [
        ("Vinilo blanco 1 galón", 65000, 48000, 19),
        ("Vinilo color 1 galón", 72000, 53000, 19),
        ("Esmalte negro 1/2 gal", 45000, 33000, 19),
        ("Brocha 2 pulg", 9000, 5000, 19),
        ("Rodillo 9 pulg", 12000, 6800, 19),
        ("Thinner 1 galón", 28000, 19000, 19),
    ],
    "Aseo & Desinfección": [
        ("Jabón en polvo 1kg", 7500, 4900, 19),
        ("Detergente líquido 1L", 12000, 7800, 19),
        ("Limpiavidrios 500ml", 6000, 3600, 19),
        ("Desinfectante pinol 1L", 5000, 2900, 19),
        ("Papel higiénico 4 und", 8000, 5200, 19),
        ("Lavaplatos 1L", 6500, 4100, 19),
    ],
    "Despensa": [
        ("Arroz blanco 1kg", 4500, 3300, 0),
        ("Frijol bola roja 1kg", 6800, 5100, 0),
        ("Azúcar blanca 1kg", 4300, 3200, 0),
        ("Harina de trigo 1kg", 4200, 3100, 0),
        ("Aceite vegetal 1L", 9500, 7000, 0),
        ("Atún en lata 170g", 6200, 4600, 19),
        ("Pasta spaghetti 500g", 3500, 2500, 0),
        ("Salsa tomate 1kg", 6500, 4700, 0),
    ],
    "Congelados": [
        ("Pollo entero (kg)", 10800, 8800, 0),
        ("Lomo de cerdo (kg)", 16500, 12500, 0),
        ("Filete de pescado (kg)", 19000, 14500, 0),
        ("Verdura congelada 500g", 8500, 5900, 0),
        ("Papas a la francesa 1kg", 9500, 6800, 0),
    ],
    "Granel & Abarrotes": [
        ("Arroz bulto 50kg", 165000, 142000, 0),
        ("Azúcar bulto 50kg", 160000, 138000, 0),
        ("Harina bulto 50kg", 155000, 132000, 0),
        ("Cebolla cabezona (kg)", 4200, 3200, 0),
        ("Tomate chonto (kg)", 3800, 2800, 0),
        ("Lenteja 2kg", 11200, 8500, 0),
        ("Café tostado 1kg", 28000, 21000, 0),
    ],
    "Papelería": [
        ("Resma carta 500 hojas", 14500, 9800, 19),
        ("Esfero azul", 1600, 800, 19),
        ("Cuaderno univers. 100h", 5800, 3500, 19),
        ("Carpeta carta", 2100, 1100, 19),
        ("Marcador permanente", 3200, 1500, 19),
        ("Cinta pegante 1/2", 1900, 900, 19),
    ],
}

SALONES = [
    # (salón, capacidad_mesas_max, [capacidades])
    ("Barra Principal", 4, [2, 2, 2, 2]),
    ("Comedor Familiar", 6, [4, 4, 6, 6, 4, 4]),
    ("Terraza al Aire", 5, [2, 4, 4, 2, 6]),
    ("Salón VIP", 3, [6, 8, 10]),
]


def main():
    db = SessionLocal()
    try:
        cat_by_name = {c.nombre: c for c in db.query(Categoria).all()}
        prod_existentes = {p.nombre for p in db.query(Producto).all()}
        salon_existentes = {s.nombre for s in db.query(Salon).all()}

        nuevas_cat = 0
        for nombre_cat, items in CATALOGO.items():
            es_nueva = nombre_cat not in cat_by_name
            cat = cat_by_name.get(nombre_cat)
            if not cat:
                cat = Categoria(nombre=nombre_cat, activa=True)
                db.add(cat)
                db.flush()
                cat_by_name[nombre_cat] = cat
                nuevas_cat += 1
            agregados = 0
            for nombre, venta, costo, imp in items:
                if nombre in prod_existentes:
                    continue
                db.add(
                    Producto(
                        empresa_id=1,
                        categoria_id=cat.id,
                        nombre=nombre,
                        descripcion=nombre,
                        precio_compra=costo,
                        costo=costo,
                        precio_venta=venta,
                        precio_mayorista=round(venta * 0.92, 2),
                        precio_minorista=round(venta * 0.97, 2),
                        precio_institucional=round(venta * 0.9, 2),
                        margen=round((venta - costo) / venta * 100, 2) if venta else 0,
                        margen_minimo=5,
                        impuesto=imp,
                        activo=True,
                        stock_minimo=5,
                        stock_maximo=200,
                        tipo="unidad",
                        sku=f"SKU-{len(prod_existentes) + 100:05d}",
                        codigo_barras=f"770{700000000000 + len(prod_existentes):08d}",
                    )
                )
                prod_existentes.add(nombre)
                agregados += 1
            print(f"  [{nombre_cat}] categoría {'nueva' if es_nueva else 'existente'}, +{agregados} productos")

        nuevos_salones = 0
        for nombre_salon, _, capacidades in SALONES:
            if nombre_salon in salon_existentes:
                continue
            salon = Salon(empresa_id=1, sucursal_id=1, nombre=nombre_salon, activo=True)
            db.add(salon)
            db.flush()
            for numero, cap in enumerate(capacidades, start=1):
                db.add(
                    Mesa(
                        salon_id=salon.id,
                        numero=f"{str(numero).zfill(2)}",
                        nombre=f"Mesas {numero}",
                        capacidad=cap,
                        estado="libre",
                    )
                )
            salon_existentes.add(nombre_salon)
            nuevos_salones += 1

        db.commit()
        salones = db.query(Salon).count()
        mesas = db.query(Mesa).count()
        productos = db.query(Producto).count()
        categorias = db.query(Categoria).count()
        print(
            f"\nOK. Categorías totales={categorias} Productos={productos} "
            f"Salones={salones} Mesas={mesas}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()