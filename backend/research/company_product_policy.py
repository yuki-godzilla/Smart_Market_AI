"""Deterministic company product and service classification policies."""

from __future__ import annotations

from collections.abc import Sequence

from backend.research.company_business_policy import (
    _company_research_is_auto_manufacturer_context,
    _company_research_is_cloud_infrastructure_context,
    _company_research_is_consumer_electronics_context,
    _company_research_is_energy_context,
    _company_research_is_healthcare_context,
    _company_research_is_heavy_machinery_context,
    _company_research_is_industrial_conglomerate_context,
    _company_research_is_materials_chemical_context,
    _company_research_is_payment_context,
    _company_research_is_railroad_context,
    _company_research_is_retail_main_context,
    _company_research_is_semiconductor_context,
    _company_research_is_software_cloud_context,
    _company_research_is_telecom_context,
    _company_research_is_trading_company_context,
    _company_research_is_utility_energy_context,
)


def _company_research_products_services(text: str) -> list[str]:
    lowered = text.lower()
    specs = (
        (
            "電気自動車",
            ("electric vehicle", "electric vehicles", "evs", "EV", "電気自動車"),
        ),
        ("自動車", ("automobile", "automotive", "自動車")),
        ("商用車", ("commercial vehicle", "commercial vehicles", "商用車")),
        ("車両", ("vehicle", "vehicles", "車両")),
        (
            "蓄電池",
            ("battery", "batteries", "energy storage", "storage systems", "蓄電池"),
        ),
        ("充電サービス", ("charging", "supercharger", "充電")),
        (
            "車載ソフトウェア",
            ("autopilot", "full self-driving", "vehicle software", "車載ソフトウェア"),
        ),
        ("部品", ("parts", "components", "部品")),
        (
            "保守・整備",
            ("maintenance", "repair", "after-sales", "aftersales", "保守", "整備"),
        ),
        (
            "建設機械",
            (
                "construction machinery",
                "heavy construction machinery",
                "construction equipment",
                "建設機械",
            ),
        ),
        (
            "産業機械",
            ("industrial machinery", "heavy machinery", "heavy equipment", "産業機械"),
        ),
        ("エンジン", ("engine", "engines", "turbine", "turbines", "エンジン")),
        (
            "鉄道サービス",
            ("railroad", "railway", "rail transport", "passenger railway", "鉄道"),
        ),
        (
            "交通インフラ",
            (
                "transportation infrastructure",
                "rail station",
                "station",
                "交通インフラ",
            ),
        ),
        (
            "デジタルシステム",
            (
                "digital systems",
                "it services",
                "information technology",
                "デジタルシステム",
            ),
        ),
        (
            "産業インフラ",
            (
                "industrial systems",
                "power grids",
                "connective industries",
                "産業インフラ",
            ),
        ),
        ("金融サービス", ("financial services", "金融")),
        ("リース", ("lease", "leasing", "リース")),
        (
            "モビリティサービス",
            ("mobility service", "mobility services", "モビリティサービス"),
        ),
        ("ソフトウェアサービス", ("software", "ソフトウェア")),
        (
            "クラウドサービス",
            ("cloud service", "cloud services", "cloud computing", "aws", "azure"),
        ),
        (
            "求人・採用サービス",
            ("recruitment", "recruiting", "employment", "job matching", "求人", "採用"),
        ),
        (
            "HRプラットフォーム",
            ("human resources", "hr technology", "staffing", "HR", "人材"),
        ),
        ("衣料品", ("apparel", "fashion", "clothing", "garment", "衣料", "アパレル")),
        ("店舗販売", ("store", "stores", "retail store", "店舗")),
        ("オンライン販売", ("e-commerce", "online sales", "online store", "EC")),
        ("ブランド運営", ("brand", "brands", "private label", "ブランド")),
        ("マーケットプレイスサービス", ("marketplace", "マーケットプレイス")),
        ("金融商品", ("financial products", "金融商品")),
        ("決済", ("payment", "payments", "決済")),
        ("カード決済", ("card payment", "card payments", "card network")),
        ("デジタル決済", ("digital payment", "digital payments")),
        ("決済ネットワーク", ("card network", "transaction", "merchant", "settlement")),
        ("加盟店サービス", ("merchant services", "加盟店")),
        ("不正検知", ("fraud", "fraud detection", "不正検知")),
        (
            "広告サービス",
            ("advertising", "advertisement", "ads", "marketing services", "広告"),
        ),
        ("保険", ("insurance", "保険")),
        ("資産運用", ("asset management", "資産運用")),
        ("銀行サービス", ("banking", "commercial bank", "銀行")),
        ("融資・クレジット", ("loan", "credit", "lending", "融資", "ローン")),
        ("センサー", ("sensor", "sensors", "センサー")),
        ("GPU", ("gpu", "graphics processing unit")),
        (
            "AIインフラ",
            ("artificial intelligence", "ai infrastructure", "accelerated computing"),
        ),
        ("データセンター向け製品", ("data center", "datacenter")),
        ("半導体", ("semiconductor", "semiconductors", "半導体")),
        (
            "医薬品",
            ("pharmaceutical", "medicine", "drug", "therapy", "医薬品", "治療薬"),
        ),
        ("医療機器", ("medical device", "medical devices", "医療機器")),
        ("診断・検査", ("diagnostics", "diagnostic", "診断", "検査")),
        ("石油・ガス", ("oil & gas", "oil and gas", "natural gas", "石油", "ガス")),
        (
            "都市ガス",
            ("city gas", "town gas", "都市ガス", "gas supply", "gas distribution"),
        ),
        (
            "電力",
            (
                "electric power",
                "electricity",
                "power generation",
                "power supply",
                "電力",
                "発電",
            ),
        ),
        ("LNG", ("lng", "liquefied natural gas")),
        ("LPG", ("lpg", "liquefied petroleum gas")),
        (
            "エネルギーサービス",
            (
                "energy services",
                "energy service",
                "energy solution",
                "エネルギーサービス",
            ),
        ),
        ("ガス機器", ("gas appliances", "gas equipment", "ガス機器")),
        (
            "エネルギーインフラ",
            ("gas pipeline", "energy infrastructure", "パイプライン"),
        ),
        (
            "生活関連サービス",
            ("life services", "life & business solutions", "生活", "ライフサービス"),
        ),
        (
            "情報ソリューション",
            (
                "information solutions",
                "information service",
                "it services",
                "情報ソリューション",
            ),
        ),
        ("不動産サービス", ("real estate", "property", "不動産")),
        (
            "材料・化学製品",
            (
                "fine materials",
                "carbon material",
                "chemical products",
                "chemicals",
                "materials segment",
                "materials business",
                "material products",
                "材料事業",
                "材料製品",
                "化学",
            ),
        ),
        ("精製・販売", ("refining", "refinery", "販売")),
        ("エネルギー開発", ("exploration", "production", "renewable", "エネルギー")),
        ("通信サービス", ("telecom", "telecommunications", "wireless", "通信")),
        ("ブロードバンド", ("broadband", "fiber optic", "optical fiber", "光回線")),
        ("測定器", ("measuring instruments", "measurement", "測定器", "計測器")),
        ("制御機器", ("control equipment", "制御機器")),
        ("検査装置", ("inspection equipment", "検査装置")),
        ("ゲーム", ("game", "gaming", "ゲーム")),
        ("音楽", ("music", "音楽")),
        ("映画", ("movie", "film", "映画")),
    )
    products = [
        label for label, keywords in specs if any(keyword in lowered for keyword in keywords)
    ]
    if _company_research_is_semiconductor_context(
        lowered
    ) and not _company_research_is_auto_manufacturer_context(lowered):
        products = [
            item for item in products if item not in {"電気自動車", "自動車", "商用車", "車両"}
        ]
    if _company_research_is_auto_manufacturer_context(lowered) and any(
        keyword in lowered for keyword in ("electric vehicle", "electric vehicles", "evs")
    ):
        products = [
            item
            for item in products
            if item not in {"金融サービス", "金融商品", "リース", "保険", "融資・クレジット"}
        ]
    if (
        _company_research_is_retail_main_context(lowered)
        and not _company_research_is_cloud_infrastructure_context(lowered)
        and not _company_research_is_auto_manufacturer_context(lowered)
    ):
        products = [
            item
            for item in products
            if item
            not in {
                "金融サービス",
                "金融商品",
                "リース",
                "保険",
                "資産運用",
                "通信サービス",
                "ブロードバンド",
            }
        ]
    if _company_research_is_payment_context(lowered) and not any(
        keyword in lowered for keyword in ("bank", "banking", "banks -")
    ):
        products = [
            item
            for item in products
            if item
            not in {
                "金融サービス",
                "金融商品",
                "オンライン販売",
                "融資・クレジット",
                "資産運用",
                "広告サービス",
            }
        ]
    if _company_research_is_trading_company_context(lowered):
        products = [item for item in products if item not in {"決済", "決済ネットワーク"}]
    if (
        not _company_research_is_auto_manufacturer_context(lowered)
        and "sector: financial" not in lowered
        and "banking" not in lowered
    ):
        products = [item for item in products if item != "リース"]
    if any(
        keyword in lowered
        for keyword in (
            "scientific & technical instruments",
            "measurement",
            "measuring",
            "sensor",
            "測定器",
            "計測",
        )
    ) and not _company_research_is_telecom_context(lowered):
        products = [item for item in products if item not in {"通信サービス", "ブロードバンド"}]
    if _company_research_is_healthcare_context(lowered):
        products = [
            item
            for item in products
            if item
            not in {
                "金融サービス",
                "金融商品",
                "決済",
                "リース",
                "保険",
                "資産運用",
                "石油・ガス",
                "精製・販売",
                "エネルギー開発",
                "通信サービス",
                "ブロードバンド",
                "店舗販売",
                "オンライン販売",
                "ブランド運営",
                "不動産サービス",
            }
        ]
    if _company_research_is_industrial_conglomerate_context(lowered):
        products = [
            item
            for item in products
            if item
            not in {
                "自動車",
                "商用車",
                "車両",
                "金融サービス",
                "金融商品",
                "決済",
                "リース",
                "保険",
                "資産運用",
                "医薬品",
                "医療機器",
                "診断・検査",
                "広告サービス",
                "ブランド運営",
                "通信サービス",
                "ブロードバンド",
                "エンジン",
            }
        ]
    if _company_research_is_railroad_context(lowered):
        products = [
            item
            for item in products
            if item
            not in {
                "自動車",
                "商用車",
                "車両",
                "蓄電池",
                "金融サービス",
                "金融商品",
                "決済",
                "リース",
                "保険",
                "資産運用",
                "医薬品",
                "医療機器",
                "診断・検査",
                "広告サービス",
                "通信サービス",
                "ブロードバンド",
                "材料・化学製品",
                "電力",
                "エンジン",
            }
        ]
    if _company_research_is_heavy_machinery_context(lowered):
        products = [
            item
            for item in products
            if item
            not in {
                "ソフトウェアサービス",
                "クラウドサービス",
                "広告サービス",
                "ブランド運営",
                "医薬品",
                "医療機器",
                "診断・検査",
                "通信サービス",
                "ブロードバンド",
            }
        ]
    if _company_research_is_consumer_electronics_context(lowered):
        products = [
            item
            for item in products
            if item
            not in {
                "金融サービス",
                "金融商品",
                "リース",
                "保険",
                "資産運用",
                "銀行サービス",
                "融資・クレジット",
            }
        ]
    if _company_research_is_software_cloud_context(lowered) and not (
        _company_research_is_retail_main_context(lowered)
        or _company_research_is_auto_manufacturer_context(lowered)
    ):
        products = [
            item
            for item in products
            if item
            not in {
                "店舗販売",
                "オンライン販売",
                "ブランド運営",
                "衣料品",
                "エネルギーインフラ",
                "不動産サービス",
            }
        ]
    if _company_research_is_energy_context(lowered):
        products = [
            item
            for item in products
            if item
            not in {
                "金融サービス",
                "金融商品",
                "決済",
                "リース",
                "保険",
                "資産運用",
                "AIインフラ",
                "データセンター向け製品",
            }
        ]
    if _company_research_is_trading_company_context(lowered):
        products = [
            item
            for item in products
            if item
            not in {
                "都市ガス",
                "電力",
                "LNG",
                "LPG",
                "エネルギーサービス",
                "ガス機器",
                "エネルギーインフラ",
                "決済",
                "決済ネットワーク",
            }
        ]
    if _company_research_is_utility_energy_context(lowered):
        products = [
            item
            for item in products
            if item
            not in {
                "金融サービス",
                "金融商品",
                "決済",
                "リース",
                "保険",
                "資産運用",
                "保守・整備",
                "ソフトウェアサービス",
                "AIインフラ",
                "データセンター向け製品",
                "通信サービス",
                "ブロードバンド",
                "精製・販売",
            }
        ]
    if _company_research_is_telecom_context(lowered):
        products = [
            item
            for item in products
            if item not in {"金融サービス", "金融商品", "決済", "保険", "資産運用"}
        ]
    if not (
        _company_research_is_materials_chemical_context(lowered)
        or _company_research_is_trading_company_context(lowered)
        or _company_research_is_energy_context(lowered)
        or _company_research_is_utility_energy_context(lowered)
    ):
        products = [item for item in products if item != "材料・化学製品"]
    if _company_research_is_utility_energy_context(lowered):
        priority = [
            "都市ガス",
            "電力",
            "LNG",
            "LPG",
            "エネルギーサービス",
            "ガス機器",
            "エネルギーインフラ",
            "生活関連サービス",
            "情報ソリューション",
            "不動産サービス",
            "材料・化学製品",
            "石油・ガス",
            "エネルギー開発",
        ]
        products = [item for item in priority if item in products] + [
            item for item in products if item not in priority
        ]
    return products


def _company_research_inferred_products_services(
    text: str,
    *,
    main_businesses: Sequence[str],
    supporting_businesses: Sequence[str],
) -> list[str]:
    lowered = text.lower()
    context = " ".join([lowered, *main_businesses, *supporting_businesses])
    inference_specs = (
        (
            (
                "railroad",
                "railway",
                "rail transport",
                "鉄道・交通インフラ",
            ),
            ("鉄道サービス", "交通インフラ", "不動産サービス"),
        ),
        (
            (
                "construction machinery",
                "heavy machinery",
                "heavy equipment",
                "産業機械・建設機械",
            ),
            ("建設機械", "産業機械", "エンジン", "部品", "保守・整備"),
        ),
        (
            (
                "digital systems and services",
                "green energy and mobility",
                "connective industries",
                "産業インフラ・デジタル",
            ),
            ("デジタルシステム", "産業インフラ", "エネルギー開発"),
        ),
        (
            (
                "自動車",
                "automotive",
                "vehicle",
                "mobility",
                "自動車事業",
                "モビリティ事業",
            ),
            ("自動車", "商用車", "部品", "金融サービス", "モビリティ関連サービス"),
        ),
        (
            ("electric vehicle", "energy storage", "charging", "auto manufacturers"),
            ("電気自動車", "蓄電池", "充電サービス", "車載ソフトウェア"),
        ),
        (
            (
                "healthcare",
                "pharmaceutical",
                "drug",
                "medicine",
                "medical device",
                "医薬品・ヘルスケア",
            ),
            ("医薬品", "医療機器", "診断・検査"),
        ),
        (
            (
                "energy",
                "oil & gas",
                "oil and gas",
                "refining",
                "exploration",
                "エネルギー",
            ),
            ("石油・ガス", "エネルギー開発", "精製・販売"),
        ),
        (
            (
                "utilities",
                "regulated gas",
                "city gas",
                "town gas",
                "natural gas distribution",
                "domestic energy",
                "international energy",
                "gas supply",
                "gas distribution",
                "ガス・エネルギーインフラ",
                "電力・エネルギー供給",
            ),
            ("都市ガス", "電力", "LNG", "エネルギーサービス", "ガス機器"),
        ),
        (
            ("telecom", "telecommunications", "wireless", "broadband", "通信サービス"),
            ("通信サービス", "ブロードバンド"),
        ),
        (
            (
                "payment",
                "payments",
                "card network",
                "transaction",
                "merchant",
                "決済ネットワーク",
            ),
            (
                "カード決済",
                "デジタル決済",
                "決済ネットワーク",
                "加盟店サービス",
                "不正検知",
            ),
        ),
        (
            (
                "human resources",
                "staffing",
                "recruitment",
                "employment",
                "人材・HRサービス",
            ),
            ("求人・採用サービス", "人材紹介", "HRプラットフォーム"),
        ),
        (
            ("apparel", "fashion", "clothing", "retail", "アパレル小売", "小売・EC"),
            ("衣料品", "店舗販売", "オンライン販売", "ブランド運営"),
        ),
        (
            ("trading company", "general trading", "sogo shosha", "総合商社・事業投資"),
            ("資源・エネルギー", "金属", "食品", "物流", "インフラ事業"),
        ),
        (
            ("software", "cloud", "saas", "platform", "ソフトウェア・クラウド"),
            ("ソフトウェアサービス", "クラウドサービス", "法人向けサービス"),
        ),
        (
            (
                "金融",
                "financial",
                "banking",
                "insurance",
                "asset management",
                "金融サービス",
            ),
            (
                "銀行サービス",
                "金融商品",
                "決済",
                "融資・クレジット",
                "保険",
                "資産運用",
            ),
        ),
        (
            (
                "electronics",
                "consumer electronics",
                "エレクトロニクス",
                "game",
                "entertainment",
            ),
            ("家電", "映像機器", "音響機器", "ゲーム", "エンタメ関連サービス"),
        ),
        (
            (
                "scientific",
                "measurement",
                "sensor",
                "control equipment",
                "科学・計測機器",
                "FAセンサー",
            ),
            ("センサー", "測定器", "制御機器", "検査装置"),
        ),
        (
            (
                "semiconductor",
                "gpu",
                "ai infrastructure",
                "accelerated computing",
                "data center",
                "半導体・GPU",
                "AI・データセンター",
            ),
            ("GPU", "AIインフラ", "データセンター向け製品", "半導体"),
        ),
    )
    for keywords, candidates in inference_specs:
        if any(keyword.lower() in context for keyword in keywords):
            return [f"{candidate}（補完候補）" for candidate in candidates]
    return []
