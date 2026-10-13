"""Generates the Power BI project (PBIP) in powerbi/GoldMarket.* from code.

    .venv\\Scripts\\python.exe -m powerbi.build_data      # refresh the CSV tables first
    .venv\\Scripts\\python.exe -m powerbi.build_report    # then (re)write the project
    start powerbi\\GoldMarket.pbip                        # opens in Power BI Desktop

Semantic model: TMDL (tables load the CSVs from powerbi/data via the DataFolder parameter).
Report: PBIR, 4 pages laid out like the reference design (KPI cards on top, white rounded
cards on a light grey page, Power BI's default blue/navy palette).
"""
import json
import shutil
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = "GoldMarket"
DATA = HERE / "data"
MODEL = HERE / f"{NAME}.SemanticModel"
REPORT = HERE / f"{NAME}.Report"

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
W, H = 1280, 720
GOLD = "PAXGUSDT"
KPI = "KPI"          # measure table ("Measures" is a reserved table name in Power BI)
# Power BI's own base theme files ship with Desktop; the report bundles a copy like Desktop does
BASE_THEMES = Path(r"C:\Program Files\Microsoft Power BI Desktop\bin\WebView2Resources"
                   r"\minerva\sharedresources\BaseThemes")
BASE_THEME = "CY26SU09"


# ---- semantic model (TMDL) ----------------------------------------------------------------
# table -> [(column, tmdl type, M type)]
TABLES = {
    "assets": [("symbol", "string"), ("name_th", "string"), ("name_en", "string"),
               ("asset_class", "string")],
    "prices_daily": [("date", "dateTime"), ("symbol", "string"), ("open", "double"),
                     ("high", "double"), ("low", "double"), ("close", "double"),
                     ("ma200", "double"), ("volume", "double"), ("quote_volume", "double"),
                     ("trades", "int64")],
    "prices_monthly": [("symbol", "string"), ("month", "dateTime"), ("close", "double"),
                       ("change_pct", "double"), ("index_2566", "double")],
    "asset_performance": [("symbol", "string"), ("name", "string"), ("start", "dateTime"),
                          ("end", "dateTime"), ("days", "int64"), ("last_close", "double"),
                          ("total_return_pct", "double"), ("ann_return_pct", "double"),
                          ("ann_volatility_pct", "double"), ("return_vol_ratio", "double"),
                          ("max_drawdown_pct", "double"), ("close_1y_ago", "double"),
                          ("close_latest", "double"), ("change_1y_pct", "double"),
                          ("latest_date", "dateTime")],
    "correlation": [("asset_a", "string"), ("asset_b", "string"), ("corr", "double")],
    "forecast": [("symbol", "string"), ("target_month", "dateTime"),
                 ("predicted_pct", "double")],
    "forecast_backtest": [("symbol", "string"), ("month", "dateTime"),
                          ("predicted_pct", "double"), ("actual_pct", "double")],
    "datasets": [("dataset_th", "string"), ("rows", "int64"), ("pairs", "int64"),
                 ("source", "string")],
    "hourly_scale": [("symbol", "string"), ("bars", "int64"), ("trades", "int64"),
                     ("quote_volume", "double"), ("quote_volume_bn", "double")],
}
M_TYPE = {"string": "type text", "double": "type number", "int64": "Int64.Type",
          "dateTime": "type date"}
FORMAT = {"double": "#,0.00", "int64": "#,0", "dateTime": "yyyy-mm-dd"}

# every per-asset table filters from assets[symbol]
RELATIONSHIPS = ["prices_daily", "prices_monthly", "asset_performance", "forecast",
                 "forecast_backtest"]

# selected asset on the detail page, or gold when nothing is picked
SEL = f'VAR s = IF(HASONEVALUE(assets[symbol]), VALUES(assets[symbol]), "{GOLD}")'
MEASURES = [
    ("ราคาทองคำล่าสุด (USD/ออนซ์)",
     f'CALCULATE(SUM(asset_performance[close_latest]), asset_performance[symbol] = "{GOLD}")',
     "$#,0"),
    ("ทองคำ เทียบปีก่อน (%)",
     f'CALCULATE(SUM(asset_performance[change_1y_pct]), asset_performance[symbol] = "{GOLD}")',
     "0.00"),
    ("ข้อมูลล่าสุด", 'FORMAT(MAX(prices_daily[date]), "MMM yyyy")', None),
    ("ข้อมูลในระบบ (แถว)", "SUM(datasets[rows])", '#,0.0,,"M"'),
    ("คาดการณ์ทองคำเดือนหน้า (%)",
     f'CALCULATE(SUM(forecast[predicted_pct]), forecast[symbol] = "{GOLD}")', "0.00"),
    ("เดือนที่ทาย", 'FORMAT(MAX(forecast[target_month]), "MMM yyyy")', None),
    ("คาดการณ์ (%)", "SUM(forecast[predicted_pct])", "0.00"),
    ("ทายไว้ (%)", "SUM(forecast_backtest[predicted_pct])", "0.00"),
    ("เกิดจริง (%)", "SUM(forecast_backtest[actual_pct])", "0.00"),
    ("ผลตอบแทน 1 ปี (%)",
     f"{SEL} RETURN CALCULATE(SUM(asset_performance[change_1y_pct]), "
     "REMOVEFILTERS(assets), asset_performance[symbol] = s)", "0.00"),
    ("ลดลงมากสุดจากจุดสูงสุด (%)",
     f"{SEL} RETURN CALCULATE(SUM(asset_performance[max_drawdown_pct]), "
     "REMOVEFILTERS(assets), asset_performance[symbol] = s)", "0.00"),
    ("ราคาปิด (USD)",
     f"{SEL} RETURN CALCULATE(AVERAGE(prices_daily[close]), "
     "REMOVEFILTERS(assets), prices_daily[symbol] = s)", "#,0.00"),
    ("ค่าเฉลี่ย 200 วัน (USD)",
     f"{SEL} RETURN CALCULATE(AVERAGE(prices_daily[ma200]), "
     "REMOVEFILTERS(assets), prices_daily[symbol] = s)", "#,0.00"),
    ("สินทรัพย์ที่เลือก",
     f'{SEL} RETURN LOOKUPVALUE(assets[name_th], assets[symbol], s)', None),
]


def tmdl_name(name: str) -> str:
    return name if name.replace("_", "").isalnum() and name.isascii() else f"'{name}'"


def table_tmdl(table: str, cols: list) -> str:
    lines = [f"table {table}", f"\tlineageTag: {uuid.uuid4()}", ""]
    for col, typ in cols:
        lines += [f"\tcolumn {col}", f"\t\tdataType: {typ}"]
        if typ in FORMAT:
            lines.append(f"\t\tformatString: {FORMAT[typ]}")
        lines += [f"\t\tlineageTag: {uuid.uuid4()}",
                  "\t\tsummarizeBy: " + ("sum" if typ in ("double", "int64") else "none"),
                  f"\t\tsourceColumn: {col}", ""]
    types = ", ".join(f'{{"{c}", {M_TYPE[t]}}}' for c, t in cols)
    m = [
        "let",
        f'    Source = Csv.Document(File.Contents(DataFolder & "{table}.csv"), '
        "[Delimiter=\",\", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),",
        "    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),",
        '    Blanks = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, '
        "Table.ColumnNames(Headers)),",
        f'    Typed = Table.TransformColumnTypes(Blanks, {{{types}}}, "en-US")',
        "in",
        "    Typed",
    ]
    lines += [f"\tpartition {table} = m", "\t\tmode: import", "\t\tsource =",
              *[f"\t\t\t\t{x}" for x in m], ""]
    return "\n".join(lines)


def measures_tmdl() -> str:
    lines = [f"table {KPI}", f"\tlineageTag: {uuid.uuid4()}", ""]
    for name, expr, fmt in MEASURES:
        lines.append(f"\tmeasure {tmdl_name(name)} = {expr}")
        if fmt:
            lines.append(f"\t\tformatString: {fmt}")
        lines += [f"\t\tlineageTag: {uuid.uuid4()}", ""]
    lines += ["\tcolumn Value", "\t\tisHidden", "\t\tdataType: string",
              f"\t\tlineageTag: {uuid.uuid4()}", "\t\tsummarizeBy: none",
              "\t\tisNameInferred", "\t\tsourceColumn: [Value]", "",
              f"\tpartition {KPI} = calculated", "\t\tmode: import",
              '\t\tsource = ROW("Value", BLANK())', ""]
    return "\n".join(lines)


def write_model() -> None:
    d = MODEL / "definition"
    (d / "tables").mkdir(parents=True)
    (MODEL / "definition.pbism").write_text(
        json.dumps({"version": "4.0", "settings": {}}, indent=2), encoding="utf-8")
    (d / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1567\n", encoding="utf-8")
    model = ["model Model", "\tculture: en-US", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
             "\tsourceQueryCulture: en-US", "\tdataAccessOptions", "\t\tlegacyRedirects",
             "\t\treturnErrorValuesAsNull", ""]
    model += [f"ref table {t}" for t in [*TABLES, KPI]]
    model += ["", "ref expression DataFolder", ""]
    (d / "model.tmdl").write_text("\n".join(model), encoding="utf-8")
    folder = str(DATA).rstrip("\\") + "\\"
    (d / "expressions.tmdl").write_text(
        f'expression DataFolder = "{folder}" meta [IsParameterQuery=true, Type="Text", '
        "IsParameterQueryRequired=true]\n"
        f"\tlineageTag: {uuid.uuid4()}\n\n", encoding="utf-8")
    for table, cols in TABLES.items():
        (d / "tables" / f"{table}.tmdl").write_text(table_tmdl(table, cols), encoding="utf-8")
    (d / "tables" / f"{KPI}.tmdl").write_text(measures_tmdl(), encoding="utf-8")
    rel = []
    for t in RELATIONSHIPS:
        rel += [f"relationship {uuid.uuid4()}", f"\tfromColumn: {t}.symbol",
                "\ttoColumn: assets.symbol", ""]
    (d / "relationships.tmdl").write_text("\n".join(rel), encoding="utf-8")


# ---- report (PBIR) ------------------------------------------------------------------------
def col(table, column):
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": column}}


def measure(name):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": KPI}}, "Property": name}}


def agg(table, column, fn=0):            # fn 0 = Sum
    return {"Aggregation": {"Expression": col(table, column), "Function": fn}}


def ref(field):
    if "Measure" in field:
        p = field["Measure"]["Property"]
        return f"{KPI}.{p}", p
    if "Aggregation" in field:
        c = field["Aggregation"]["Expression"]["Column"]
        t, p = c["Expression"]["SourceRef"]["Entity"], c["Property"]
        return f"Sum({t}.{p})", p
    t, p = field["Column"]["Expression"]["SourceRef"]["Entity"], field["Column"]["Property"]
    return f"{t}.{p}", p


def proj(field, display=None):
    q, n = ref(field)
    p = {"field": field, "queryRef": q, "nativeQueryRef": n}
    if display:
        p["displayName"] = display
    return p


def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def text(s):
    return lit("'" + s.replace("'", "''") + "'")


def symbol_filter(name, table, symbols):
    return {"name": name, "field": col(table, "symbol"), "type": "Categorical",
            "filter": {"Version": 2, "From": [{"Name": "a", "Entity": table, "Type": 0}],
                       "Where": [{"Condition": {"In": {
                           "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "a"}},
                                                       "Property": "symbol"}}],
                           "Values": [[{"Literal": {"Value": f"'{s}'"}}] for s in symbols]}}}]},
            "howCreated": "User"}


def container(title, subtitle=None):
    obj = {"title": [{"properties": {"show": lit("true"), "text": text(title),
                                     "fontSize": lit("11D"), "bold": lit("true")}}]}
    if subtitle:
        obj["subTitle"] = [{"properties": {"show": lit("true"), "text": text(subtitle)}}]
    return obj


class Page:
    def __init__(self, name, display):
        self.name, self.display, self.visuals = name, display, []

    def add(self, vtype, x, y, w, h, roles=None, title=None, subtitle=None, objects=None,
            sort=None, filters=None, extra=None):
        v = {"visualType": vtype, "drillFilterOtherVisuals": True}
        if roles:
            v["query"] = {"queryState": {r: {"projections": ps} for r, ps in roles.items()}}
            if sort:
                v["query"]["sortDefinition"] = {"sort": [{"field": sort[0], "direction": sort[1]}],
                                                "isDefaultSort": False}
        if objects:
            v["objects"] = objects
        if title:
            v["visualContainerObjects"] = container(title, subtitle)
        if extra:
            v.update(extra)
        vid = f"v{len(self.visuals) + 1:02d}{uuid.uuid4().hex[:14]}"
        body = {"$schema": f"{SCHEMA}/visualContainer/1.0.0/schema.json", "name": vid,
                "position": {"x": x, "y": y, "z": len(self.visuals) * 1000, "width": w,
                             "height": h, "tabOrder": len(self.visuals) * 1000},
                "visual": v}
        if filters:
            body["filterConfig"] = {"filters": filters}
        self.visuals.append(body)

    def card(self, x, y, w, h, title, field):
        self.add("card", x, y, w, h, {"Values": [proj(field)]}, title=title,
                 objects={"labels": [{"properties": {"fontSize": lit("32D"),
                                                     "bold": lit("true")}}],
                          "categoryLabels": [{"properties": {"show": lit("false")}}]})

    def write(self, root):
        pd = root / self.name
        (pd / "visuals").mkdir(parents=True)
        (pd / "page.json").write_text(json.dumps({
            "$schema": f"{SCHEMA}/page/1.0.0/schema.json", "name": self.name,
            "displayName": self.display, "displayOption": "FitToPage",
            "height": H, "width": W}, ensure_ascii=False, indent=2), encoding="utf-8")
        for v in self.visuals:
            vd = pd / "visuals" / v["name"]
            vd.mkdir()
            (vd / "visual.json").write_text(json.dumps(v, ensure_ascii=False, indent=2),
                                            encoding="utf-8")


def kpi_row(page, cards, y=16, h=112):
    gap, n = 12, len(cards)
    w = (W - 32 - gap * (n - 1)) // n
    for i, (title, field) in enumerate(cards):
        page.card(16 + i * (w + gap), y, w, h, title, field)


def bars(page, x, y, w, h, title, subtitle, value, display):
    page.add("clusteredBarChart", x, y, w, h,
             {"Category": [proj(col("assets", "name_th"), "สินทรัพย์")],
              "Y": [proj(value, display)]},
             title=title, subtitle=subtitle, sort=(value, "Descending"),
             objects={"categoryAxis": [{"properties": {"showAxisTitle": lit("false")}}],
                      "valueAxis": [{"properties": {"showAxisTitle": lit("false")}}],
                      "dataPoint": [{"properties": {"fill": {"solid": {"color": lit("'#118DFF'")}}}}]})


def build_pages():
    top = 16 + 112 + 14
    body_h = H - top - 16

    p1 = Page("overview", "ภาพรวม")
    kpi_row(p1, [("ราคาทองคำล่าสุด (USD/ออนซ์)", measure("ราคาทองคำล่าสุด (USD/ออนซ์)")),
                 ("ทองคำ เทียบปีก่อน (%)", measure("ทองคำ เทียบปีก่อน (%)")),
                 ("ข้อมูลล่าสุด", measure("ข้อมูลล่าสุด")),
                 ("ข้อมูลในระบบ (แถว)", measure("ข้อมูลในระบบ (แถว)"))])
    p1.add("lineChart", 16, top, 760, body_h,
           {"Category": [proj(col("prices_monthly", "month"), "เดือน")],
            "Y": [proj(agg("prices_monthly", "index_2566"), "ดัชนีราคา")],
            "Series": [proj(col("assets", "name_th"), "สินทรัพย์")]},
           title="ดัชนีราคารายเดือน ตามสินทรัพย์ (ปี 2566 = 100)",
           subtitle="ดัชนีราคา by เดือน and สินทรัพย์",
           objects={"legend": [{"properties": {"show": lit("true"), "position": lit("'Bottom'")}}],
                    "categoryAxis": [{"properties": {"showAxisTitle": lit("false")}}],
                    "valueAxis": [{"properties": {"showAxisTitle": lit("false")}}]},
           filters=[symbol_filter("assetsShown", "assets",
                                  [GOLD, "BTCUSDT", "ETHUSDT", "BNBUSDT", "EURUSDT", "GBPUSDT"])])
    bars(p1, 16 + 760 + 12, top, W - 32 - 760 - 12, body_h,
         "ผลตอบแทน 1 ปีล่าสุด ตามสินทรัพย์ (%)", "ผลตอบแทน 1 ปี (%) by สินทรัพย์",
         agg("asset_performance", "change_1y_pct"), "ผลตอบแทน 1 ปี (%)")

    p2 = Page("compare", "เปรียบเทียบสินทรัพย์")
    half = (W - 32 - 12) // 2
    bars(p2, 16, 16, half, H - 32, "ผลตอบแทนเฉลี่ยต่อปี ตามสินทรัพย์ (%)",
         "ผลตอบแทนต่อปี (%) by สินทรัพย์", agg("asset_performance", "ann_return_pct"),
         "ผลตอบแทนต่อปี (%)")
    bars(p2, 16 + half + 12, 16, half, H - 32, "ความผันผวนต่อปี ตามสินทรัพย์ (%)",
         "ความผันผวนต่อปี (%) by สินทรัพย์", agg("asset_performance", "ann_volatility_pct"),
         "ความผันผวนต่อปี (%)")

    p3 = Page("forecast", "คาดการณ์")
    p3.card(16, 16, 300, 112, "คาดการณ์ทองคำเดือนหน้า (%)", measure("คาดการณ์ทองคำเดือนหน้า (%)"))
    p3.card(328, 16, 300, 112, "เดือนที่ทาย", measure("เดือนที่ทาย"))
    p3.add("textbox", 640, 16, W - 656, 112, extra={"objects": {"general": [{"properties": {
        "paragraphs": [{"textRuns": [{"value": "วิธีคาดการณ์: แบบจำลองสถิติ AR(1) จาก % เปลี่ยนแปลง"
                                               "รายเดือนย้อนหลัง 36 เดือน ของแต่ละสินทรัพย์ "
                                               "(ข้อมูลจริงจาก Binance) · เป็นการประมาณทางสถิติ "
                                               "ไม่ใช่คำแนะนำการลงทุน",
                                      "textStyle": {"fontSize": "11pt", "color": "#605E5C"}}]}]}}]}})
    p3.add("tableEx", 16, top, 520, body_h,
           {"Values": [proj(col("assets", "name_th"), "สินทรัพย์"),
                       proj(measure("คาดการณ์ (%)"), "คาดการณ์เดือนหน้า (%)")]},
           title="คาดการณ์ % เปลี่ยนแปลงเดือนหน้า ตามสินทรัพย์",
           sort=(measure("คาดการณ์ (%)"), "Descending"),
           objects={"total": [{"properties": {"totals": lit("false")}}]})
    p3.add("lineChart", 16 + 520 + 12, top, W - 32 - 520 - 12, body_h,
           {"Category": [proj(col("forecast_backtest", "month"), "เดือน")],
            "Y": [proj(measure("ทายไว้ (%)"), "ทายไว้ (%)"),
                  proj(measure("เกิดจริง (%)"), "เกิดจริง (%)")]},
           title="ทายไว้ vs เกิดจริง (ทองคำ % เปลี่ยนแปลงรายเดือน)",
           subtitle="ทายไว้ (%) และ เกิดจริง (%) by เดือน",
           objects={"legend": [{"properties": {"show": lit("true"), "position": lit("'Bottom'")}}],
                    "categoryAxis": [{"properties": {"showAxisTitle": lit("false")}}],
                    "valueAxis": [{"properties": {"showAxisTitle": lit("false")}}],
                    "lineStyles": [{"properties": {"lineInterpolation": lit("'smooth'")}}]},
           filters=[symbol_filter("goldOnly", "forecast_backtest", [GOLD])])

    p4 = Page("detail", "รายละเอียดสินทรัพย์")
    p4.add("slicer", 16, 16, 300, 112, {"Values": [proj(col("assets", "name_th"), "สินทรัพย์")]},
           title="เลือกสินทรัพย์ (ค่าเริ่มต้น: ทองคำ)",
           objects={"data": [{"properties": {"mode": lit("'Dropdown'")}}],
                    "selection": [{"properties": {"singleSelect": lit("true")}}],
                    "header": [{"properties": {"show": lit("false")}}]})
    p4.card(328, 16, 300, 112, "ผลตอบแทน 1 ปี (%)", measure("ผลตอบแทน 1 ปี (%)"))
    p4.card(640, 16, 300, 112, "ลดลงมากสุดจากจุดสูงสุด (%)", measure("ลดลงมากสุดจากจุดสูงสุด (%)"))
    p4.card(952, 16, W - 968, 112, "สินทรัพย์ที่แสดง", measure("สินทรัพย์ที่เลือก"))
    p4.add("lineChart", 16, top, 760, body_h,
           {"Category": [proj(col("prices_daily", "date"), "วันที่")],
            "Y": [proj(measure("ราคาปิด (USD)"), "ราคาปิด (USD)"),
                  proj(measure("ค่าเฉลี่ย 200 วัน (USD)"), "ค่าเฉลี่ย 200 วัน (USD)")]},
           title="ราคาปิด vs ค่าเฉลี่ย 200 วัน (USD)",
           subtitle="ราคาปิด (USD) and ค่าเฉลี่ย 200 วัน (USD) by วันที่",
           objects={"legend": [{"properties": {"show": lit("true"), "position": lit("'Bottom'")}}],
                    "categoryAxis": [{"properties": {"showAxisTitle": lit("false")}}],
                    "valueAxis": [{"properties": {"showAxisTitle": lit("false")}}]})
    p4.add("tableEx", 16 + 760 + 12, top, W - 32 - 760 - 12, body_h,
           {"Values": [proj(col("assets", "name_th"), "สินทรัพย์"),
                       proj(agg("asset_performance", "close_1y_ago"), "ราคา 1 ปีก่อน (USD)"),
                       proj(agg("asset_performance", "close_latest"), "ราคาล่าสุด (USD)"),
                       proj(agg("asset_performance", "change_1y_pct"), "เปลี่ยนแปลง (%)")]},
           title="ราคาตอนนี้ vs 1 ปีก่อน",
           sort=(agg("asset_performance", "change_1y_pct"), "Descending"),
           objects={"total": [{"properties": {"totals": lit("false")}}]})
    return [p1, p2, p3, p4]


THEME = {
    "name": "GoldMarket",
    "dataColors": ["#118DFF", "#12239E", "#E66C37", "#6B007B", "#E044A7", "#744EC2",
                   "#D9B300", "#D64550", "#197278", "#1AAB40"],
    "background": "#FFFFFF", "foreground": "#252423", "tableAccent": "#118DFF",
    "textClasses": {"callout": {"fontSize": 32, "fontFace": "Segoe UI Semibold", "color": "#252423"},
                    "title": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": "#252423"},
                    "label": {"fontSize": 9, "fontFace": "Segoe UI", "color": "#605E5C"}},
    "visualStyles": {
        "*": {"*": {
            "background": [{"show": True, "color": {"solid": {"color": "#FFFFFF"}},
                            "transparency": 0}],
            "border": [{"show": True, "color": {"solid": {"color": "#E1DFDD"}}, "radius": 10}],
            "dropShadow": [{"show": False}],
            "padding": [{"top": 10, "bottom": 10, "left": 12, "right": 12}],
            "title": [{"show": True, "fontSize": 11, "fontColor": {"solid": {"color": "#252423"}}}],
            "subTitle": [{"fontColor": {"solid": {"color": "#605E5C"}}}],
        }},
        "page": {"*": {
            "background": [{"color": {"solid": {"color": "#F3F2F1"}}, "transparency": 0}],
            "outspace": [{"color": {"solid": {"color": "#2B2B2B"}}, "transparency": 0}],
        }},
    },
}


def write_report() -> None:
    d = REPORT / "definition"
    (d / "pages").mkdir(parents=True)
    res = REPORT / "StaticResources" / "RegisteredResources"
    res.mkdir(parents=True)
    base = REPORT / "StaticResources" / "SharedResources" / "BaseThemes"
    base.mkdir(parents=True)
    shutil.copy(BASE_THEMES / f"{BASE_THEME}.json", base)
    (res / "GoldMarketTheme.json").write_text(json.dumps(THEME, indent=2), encoding="utf-8")
    (REPORT / "definition.pbir").write_text(json.dumps(
        {"version": "4.0", "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}},
        indent=2), encoding="utf-8")
    (d / "version.json").write_text(json.dumps(
        {"$schema": f"{SCHEMA}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"},
        indent=2), encoding="utf-8")
    (d / "report.json").write_text(json.dumps({
        "$schema": f"{SCHEMA}/report/1.0.0/schema.json",
        "themeCollection": {"baseTheme": {"name": BASE_THEME, "reportVersionAtImport": "5.55",
                                          "type": "SharedResources"},
                            "customTheme": {"name": "GoldMarketTheme.json",
                                            "reportVersionAtImport": "5.55",
                                            "type": "RegisteredResources"}},
        "layoutOptimization": "None",
        "resourcePackages": [{"name": "SharedResources", "type": "SharedResources",
                              "items": [{"name": BASE_THEME, "path": f"BaseThemes/{BASE_THEME}.json",
                                         "type": "BaseTheme"}]},
                             {"name": "RegisteredResources", "type": "RegisteredResources",
                              "items": [{"name": "GoldMarketTheme.json",
                                         "path": "GoldMarketTheme.json",
                                         "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True,
                     "defaultDrillFilterOtherVisuals": True,
                     "useEnhancedTooltips": True},
    }, indent=2), encoding="utf-8")
    pages = build_pages()
    for p in pages:
        p.write(d / "pages")
    (d / "pages" / "pages.json").write_text(json.dumps({
        "$schema": f"{SCHEMA}/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p.name for p in pages], "activePageName": pages[0].name}, indent=2),
        encoding="utf-8")


def main() -> None:
    for p in (MODEL, REPORT):
        if p.exists():
            shutil.rmtree(p)
    write_model()
    write_report()
    (HERE / f"{NAME}.pbip").write_text(json.dumps({
        "version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True}}, indent=2), encoding="utf-8")
    print(f"wrote {HERE / (NAME + '.pbip')}")


if __name__ == "__main__":
    main()
