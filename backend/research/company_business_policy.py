"""Deterministic company business classification policies."""

from __future__ import annotations

import re
from collections.abc import Sequence


def _unique_text(values: Sequence[str]) -> list[str]:
    unique: list[str] = []
    for value in values:
        cleaned = re.sub(r"\s+", " ", value).strip()
        if cleaned and cleaned not in unique:
            unique.append(cleaned)
    return unique


def _company_research_business_terms(text: str) -> list[str]:
    lowered = text.lower()
    specs = (
        (
            "自動車事業",
            (
                "自動車",
                "車両",
                "vehicle",
                "vehicles",
                "automotive",
                "auto manufacturers",
                "motor",
            ),
        ),
        (
            "半導体・GPU",
            (
                "semiconductor",
                "semiconductors",
                "gpu",
                "graphics processing unit",
                "accelerated computing",
                "半導体",
            ),
        ),
        (
            "AI・データセンター",
            (
                "artificial intelligence",
                "ai infrastructure",
                "data center",
                "datacenter",
                "データセンター",
            ),
        ),
        (
            "半導体製造装置",
            ("semiconductor equipment", "半導体製造装置", "wafer", "lithography"),
        ),
        (
            "FAセンサー・制御機器",
            ("fa sensor", "factory automation", "control equipment", "制御機器"),
        ),
        (
            "科学・計測機器",
            (
                "scientific instrument",
                "measurement",
                "measuring",
                "sensor",
                "測定器",
                "計測",
            ),
        ),
        (
            "産業インフラ・デジタル",
            (
                "industry: conglomerates",
                "industrial conglomerate",
                "digital systems and services",
                "green energy and mobility",
                "connective industries",
                "industrial systems",
                "power grids",
                "産業インフラ",
            ),
        ),
        (
            "産業機械・建設機械",
            (
                "farm & heavy construction machinery",
                "construction machinery",
                "heavy machinery",
                "heavy equipment",
                "earthmoving",
                "industrial machinery",
                "建設機械",
                "産業機械",
            ),
        ),
        (
            "鉄道・交通インフラ",
            (
                "industry: railroads",
                "railroad",
                "railway",
                "rail transport",
                "passenger railway",
                "鉄道",
                "交通インフラ",
            ),
        ),
        ("モビリティ事業", ("モビリティ", "mobility")),
        (
            "エレクトロニクス",
            ("electronics", "consumer electronics", "家電", "映像機器", "音響機器"),
        ),
        (
            "ゲーム・エンタメ",
            (
                "game",
                "gaming",
                "music",
                "movie",
                "entertainment",
                "ゲーム",
                "音楽",
                "映画",
            ),
        ),
        (
            "ソフトウェア・クラウド",
            (
                "software",
                "cloud",
                "cloud computing",
                "cloud services",
                "saas",
                "platform",
                "aws",
                "amazon web services",
                "azure",
                "enterprise services",
                "ソフトウェア",
                "クラウド",
            ),
        ),
        (
            "広告・マーケティング",
            ("advertising", "advertisement", "ads", "marketing services", "広告"),
        ),
        (
            "決済ネットワーク",
            (
                "payment",
                "payments",
                "card network",
                "transaction",
                "merchant",
                "fintech",
                "digital payment",
                "settlement",
            ),
        ),
        (
            "銀行・金融サービス",
            (
                "sector: financial services",
                "banks -",
                "banking",
                "commercial banking",
                "investment banking",
                "asset management",
                "credit",
                "loan",
                "securities",
                "銀行",
                "証券",
            ),
        ),
        (
            "医薬品・ヘルスケア",
            (
                "sector: healthcare",
                "pharmaceutical",
                "healthcare",
                "medical device",
                "medicine",
                "biotech",
                "drug",
                "therapy",
                "diagnostics",
                "医薬品",
                "医療機器",
            ),
        ),
        (
            "エネルギー",
            (
                "sector: energy",
                "oil & gas",
                "oil and gas",
                "refining",
                "exploration",
                "production",
                "renewable",
                "石油",
                "ガス",
                "エネルギー",
            ),
        ),
        (
            "ガス・エネルギーインフラ",
            (
                "sector: utilities",
                "industry: utilities",
                "utilities - regulated gas",
                "gas utilities",
                "natural gas distribution",
                "city gas",
                "town gas",
                "gas distribution",
                "gas supply",
                "gas pipeline",
                "都市ガス",
                "ガス供給",
                "エネルギー供給",
                "公益",
                "インフラ",
            ),
        ),
        (
            "電力・エネルギー供給",
            (
                "electric power",
                "electricity",
                "power generation",
                "power supply",
                "domestic energy",
                "international energy",
                "電力",
                "発電",
                "エネルギー供給",
            ),
        ),
        (
            "通信サービス",
            (
                "telecom services",
                "telecommunications",
                "wireless",
                "broadband",
                "通信",
            ),
        ),
        (
            "人材・HRサービス",
            (
                "human resources",
                "staffing",
                "recruitment",
                "recruiting",
                "employment",
                "job matching",
                "hr technology",
                "人材",
                "採用",
                "求人",
            ),
        ),
        (
            "総合商社・事業投資",
            (
                "trading company",
                "general trading",
                "sogo shosha",
                "industrial finance",
                "事業投資",
                "総合商社",
            ),
        ),
        (
            "アパレル小売",
            (
                "apparel",
                "fashion",
                "clothing",
                "brand",
                "private label",
                "SPA",
                "衣料",
                "アパレル",
            ),
        ),
        (
            "小売・EC",
            ("retail", "e-commerce", "marketplace", "store", "apparel", "小売", "EC"),
        ),
    )
    labels = [label for label, keywords in specs if any(keyword in lowered for keyword in keywords)]
    finance_main_context = (
        "sector: financial" in lowered
        or "financial sector" in lowered
        or "banking" in lowered
        or "asset management" in lowered
        or "銀行" in lowered
        or "証券" in lowered
    )
    if finance_main_context and "金融サービス" not in labels and "銀行・金融サービス" not in labels:
        labels.append("金融サービス")
    return labels


def _company_research_filter_main_businesses(
    text: str,
    businesses: Sequence[str],
) -> list[str]:
    lowered = text.lower()
    finance_main_context = (
        "sector: financial" in lowered
        or "financial sector" in lowered
        or "banking" in lowered
        or "asset management" in lowered
        or "銀行" in lowered
        or "証券" in lowered
    )
    auto_manufacturer_context = _company_research_is_auto_manufacturer_context(lowered)
    software_cloud_context = _company_research_is_software_cloud_context(lowered)
    retail_main_context = _company_research_is_retail_main_context(lowered)
    payment_context = _company_research_is_payment_context(lowered)
    hr_context = _company_research_is_hr_services_context(lowered)
    trading_context = _company_research_is_trading_company_context(lowered)
    cloud_infra_context = _company_research_is_cloud_infrastructure_context(lowered)
    bank_context = any(
        keyword in lowered
        for keyword in (
            "bank",
            "banking",
            "banks -",
            "commercial banking",
            "investment banking",
        )
    )
    healthcare_context = _company_research_is_healthcare_context(lowered)
    energy_context = _company_research_is_energy_context(lowered)
    utility_energy_context = _company_research_is_utility_energy_context(lowered)
    telecom_context = _company_research_is_telecom_context(lowered)
    consumer_electronics_context = _company_research_is_consumer_electronics_context(lowered)
    industrial_conglomerate_context = _company_research_is_industrial_conglomerate_context(lowered)
    heavy_machinery_context = _company_research_is_heavy_machinery_context(lowered)
    railroad_context = _company_research_is_railroad_context(lowered)
    auto_related_main = {"自動車事業", "モビリティ事業", "自動車・モビリティ"}
    software_related_main = {"ソフトウェア・クラウド", "ソフトウェア・サービス"}
    finance_related_main = {"金融サービス", "銀行・金融サービス"}
    utility_related_main = {"ガス・エネルギーインフラ", "電力・エネルギー供給"}
    industrial_related_main = {
        "産業インフラ・デジタル",
        "産業機械・建設機械",
        "鉄道・交通インフラ",
    }
    filtered = [
        item
        for item in businesses
        if not (item == "金融サービス" and not finance_main_context)
        and not (payment_context and not bank_context and item == "金融サービス")
        and not (item == "銀行・金融サービス" and not finance_main_context)
        and not (payment_context and not bank_context and item == "銀行・金融サービス")
        and not (not auto_manufacturer_context and item in auto_related_main)
        and not (auto_manufacturer_context and item in {"小売・EC", "アパレル小売"})
        and not (auto_manufacturer_context and item == "決済ネットワーク")
        and not (item == "小売・EC" and software_cloud_context and not retail_main_context)
        and not (item == "アパレル小売" and not retail_main_context)
        and not (retail_main_context and item in software_related_main and not cloud_infra_context)
        and not (retail_main_context and item == "通信サービス")
        and not (finance_main_context and item == "小売・EC")
        and not (bank_context and item == "決済ネットワーク")
        and not (payment_context and not bank_context and item == "銀行・金融サービス")
        and not (payment_context and item == "広告・マーケティング")
        and not (hr_context and item == "通信サービス")
        and not (
            trading_context
            and item
            in (
                software_related_main
                | industrial_related_main
                | utility_related_main
                | {"小売・EC", "アパレル小売", "決済ネットワーク", "エネルギー"}
            )
        )
        and not (not healthcare_context and item == "医薬品・ヘルスケア")
        and not (not energy_context and item == "エネルギー")
        and not (not telecom_context and item == "通信サービス")
        and not (not industrial_conglomerate_context and item == "産業インフラ・デジタル")
        and not (not heavy_machinery_context and item == "産業機械・建設機械")
        and not (not railroad_context and item == "鉄道・交通インフラ")
        and not (finance_main_context and item in software_related_main)
        and not (healthcare_context and item in finance_related_main | software_related_main)
        and not (healthcare_context and item in {"小売・EC", "アパレル小売"})
        and not (
            energy_context
            and item in finance_related_main | software_related_main | {"AI・データセンター"}
        )
        and not (
            utility_energy_context
            and item
            in (
                finance_related_main
                | software_related_main
                | {
                    "自動車事業",
                    "モビリティ事業",
                    "小売・EC",
                    "通信サービス",
                    "AI・データセンター",
                }
            )
        )
        and not (telecom_context and item in finance_related_main | software_related_main)
        and not (consumer_electronics_context and item in finance_related_main)
        and not (
            industrial_conglomerate_context
            and item
            in (
                auto_related_main
                | finance_related_main
                | software_related_main
                | {
                    "医薬品・ヘルスケア",
                    "広告・マーケティング",
                    "小売・EC",
                    "アパレル小売",
                    "部品・保守",
                }
            )
        )
        and not (
            heavy_machinery_context
            and item
            in (
                finance_related_main
                | software_related_main
                | {"エレクトロニクス", "医薬品・ヘルスケア", "広告・マーケティング"}
            )
        )
        and not (
            railroad_context
            and item
            in (
                auto_related_main
                | finance_related_main
                | software_related_main
                | utility_related_main
                | {
                    "医薬品・ヘルスケア",
                    "広告・マーケティング",
                    "エレクトロニクス",
                    "小売・EC",
                    "エネルギー",
                    "部品・保守",
                }
            )
        )
        and not (
            item == "総合商社・事業投資" and industrial_conglomerate_context and not trading_context
        )
        and item not in {"部品・アフターサービス", "部品・保守", "リース", "ソフトウェア"}
    ]
    if trading_context:
        filtered = ["総合商社・事業投資"] + [
            item
            for item in filtered
            if item
            not in (
                industrial_related_main | utility_related_main | {"エネルギー", "決済ネットワーク"}
            )
        ]
    if railroad_context and "鉄道・交通インフラ" in filtered:
        priority = ["鉄道・交通インフラ"]
        filtered = [item for item in priority if item in filtered] + [
            item for item in filtered if item not in priority
        ]
    if heavy_machinery_context and "産業機械・建設機械" in filtered:
        priority = ["産業機械・建設機械"]
        filtered = [item for item in priority if item in filtered] + [
            item for item in filtered if item not in priority
        ]
    if industrial_conglomerate_context and "産業インフラ・デジタル" in filtered:
        priority = ["産業インフラ・デジタル", "エネルギー"]
        filtered = [item for item in priority if item in filtered] + [
            item for item in filtered if item not in priority
        ]
    if utility_energy_context and any(item in filtered for item in utility_related_main):
        priority = ["ガス・エネルギーインフラ", "電力・エネルギー供給", "エネルギー"]
        filtered = [item for item in priority if item in filtered] + [
            item for item in filtered if item not in priority
        ]
        if "ガス・エネルギーインフラ" in filtered:
            filtered = [item for item in filtered if item != "エネルギー"]
    if "銀行・金融サービス" in filtered:
        filtered = [item for item in filtered if item != "金融サービス"]
    elif bank_context and finance_main_context and not consumer_electronics_context:
        filtered.insert(0, "銀行・金融サービス")
    if "ソフトウェア・クラウド" in filtered:
        filtered = [item for item in filtered if item != "ソフトウェア・サービス"]
    if retail_main_context and cloud_infra_context:
        priority = [
            "小売・EC",
            "ソフトウェア・クラウド",
            "広告・マーケティング",
            "AI・データセンター",
            "ゲーム・エンタメ",
        ]
        filtered = [item for item in priority if item in filtered] + [
            item for item in filtered if item not in priority
        ]
    return _unique_text(filtered)[:5]


def _company_research_is_semiconductor_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "industry: semiconductors",
            "semiconductor",
            "semiconductors",
            "gpu",
            "accelerated computing",
            "ai infrastructure",
            "data center",
            "datacenter",
        )
    )


def _company_research_is_auto_manufacturer_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "industry: auto manufacturers",
            "auto manufacturers",
            "automobile manufacturer",
            "motor corporation",
        )
    )


def _company_research_is_software_cloud_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "software",
            "cloud",
            "saas",
            "platform",
            "azure",
            "enterprise services",
        )
    )


def _company_research_is_cloud_infrastructure_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "cloud computing",
            "cloud infrastructure",
            "cloud services",
            "aws",
            "amazon web services",
            "azure",
            "google cloud",
        )
    )


def _company_research_is_payment_context(lowered_text: str) -> bool:
    strong_keywords = (
        "industry: credit services",
        "card network",
        "payment network",
        "payments network",
        "transaction processing",
        "merchant services",
        "digital payment",
        "settlement network",
    )
    if any(keyword in lowered_text for keyword in strong_keywords):
        return True
    return "sector: financial" in lowered_text and any(
        keyword in lowered_text for keyword in ("payment", "payments", "transaction", "merchant")
    )


def _company_research_is_hr_services_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "human resources",
            "staffing",
            "recruitment",
            "recruiting",
            "employment",
            "job matching",
            "hr technology",
            "人材",
            "採用",
            "求人",
        )
    )


def _company_research_is_trading_company_context(lowered_text: str) -> bool:
    if any(
        keyword in lowered_text
        for keyword in (
            "trading company",
            "general trading",
            "sogo shosha",
            "事業投資",
            "総合商社",
        )
    ):
        return True
    if "sector: industrials" not in lowered_text or "industry: conglomerates" not in lowered_text:
        return False
    diversified_trading_terms = (
        "natural gas",
        "industrial materials",
        "petroleum",
        "chemicals solution",
        "mineral resources",
        "industrial infrastructure",
        "automotive & mobility",
        "food industry",
        "consumer industry",
        "power solution",
        "urban development",
    )
    return sum(term in lowered_text for term in diversified_trading_terms) >= 4


def _company_research_is_industrial_conglomerate_context(lowered_text: str) -> bool:
    if _company_research_is_trading_company_context(lowered_text):
        return False
    return (
        "sector: industrials" in lowered_text
        and ("industry: conglomerates" in lowered_text or "industrial conglomerate" in lowered_text)
    ) or any(
        keyword in lowered_text
        for keyword in (
            "digital systems and services",
            "green energy and mobility",
            "connective industries",
            "industrial systems",
            "power grids",
        )
    )


def _company_research_is_heavy_machinery_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "industry: farm & heavy construction machinery",
            "construction machinery",
            "heavy construction machinery",
            "heavy machinery",
            "heavy equipment",
            "earthmoving",
            "industrial machinery",
        )
    )


def _company_research_is_consumer_electronics_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "industry: consumer electronics",
            "consumer electronics",
            "electronic gaming & multimedia",
        )
    )


def _company_research_is_railroad_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "industry: railroads",
            "railroad",
            "railway",
            "rail transport",
            "passenger railway",
            "rail station",
        )
    )


def _company_research_is_materials_chemical_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "industry: chemicals",
            "specialty chemicals",
            "chemical manufacturing",
            "chemical products",
            "fine materials",
            "carbon material",
            "materials segment",
            "materials business",
            "material products",
            "材料事業",
            "材料製品",
            "化学",
        )
    )


def _company_research_is_apparel_retail_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "apparel",
            "fashion",
            "clothing",
            "private label",
            "specialty retail",
            "衣料",
            "アパレル",
        )
    )


def _company_research_is_retail_main_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "industry: internet retail",
            "industry: apparel retail",
            "industry: specialty retail",
            "sector: consumer cyclical",
            "retail trade",
            "retailer",
            "e-commerce company",
        )
    )


def _company_research_is_healthcare_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "sector: healthcare",
            "industry: healthcare",
            "industry: pharmaceutical",
            "medical device",
            "drug manufacturers",
            "biotech",
        )
    )


def _company_research_is_energy_context(lowered_text: str) -> bool:
    return _company_research_is_utility_energy_context(lowered_text) or any(
        keyword in lowered_text
        for keyword in (
            "sector: energy",
            "oil & gas",
            "oil and gas",
            "refining",
            "exploration",
            "production",
        )
    )


def _company_research_is_utility_energy_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "sector: utilities",
            "industry: utilities",
            "utilities - regulated gas",
            "gas utilities",
            "natural gas distribution",
            "city gas",
            "town gas",
            "gas distribution",
            "gas supply",
            "gas pipeline",
            "electric power",
            "electricity",
            "power generation",
            "domestic energy",
            "international energy",
            "都市ガス",
            "ガス供給",
            "電力",
            "発電",
            "エネルギー供給",
            "公益",
            "インフラ",
        )
    )


def _company_research_is_telecom_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "telecom services",
            "telecommunications",
            "wireless",
            "broadband",
            "mobile network",
            "fixed-line",
            "fiber optic",
        )
    )


def _company_research_supporting_business_terms(
    text: str,
    *,
    main_businesses: Sequence[str],
) -> list[str]:
    lowered = text.lower()
    specs = (
        ("金融サービス", ("financial services", "金融")),
        ("リース", ("lease", "leasing", "リース")),
        (
            "部品・アフターサービス",
            ("parts", "components", "maintenance", "repair", "部品", "保守", "整備"),
        ),
        ("ソフトウェア", ("software", "ソフトウェア")),
        ("保険", ("insurance", "保険")),
        ("資産運用", ("asset management", "資産運用")),
        (
            "海外エネルギー",
            ("international energy", "overseas energy", "海外エネルギー"),
        ),
        (
            "ライフサービス",
            (
                "life & business solutions",
                "life services",
                "lifestyle",
                "生活",
                "ライフサービス",
            ),
        ),
        ("不動産", ("real estate", "property", "不動産")),
        (
            "情報ソリューション",
            (
                "information solutions",
                "information service",
                "it services",
                "情報ソリューション",
            ),
        ),
        (
            "材料・化学",
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
    )
    main_set = set(main_businesses)
    return [
        label
        for label, keywords in specs
        if label not in main_set and any(keyword in lowered for keyword in keywords)
    ]


def _company_research_filter_supporting_businesses(
    text: str,
    businesses: Sequence[str],
    *,
    main_businesses: Sequence[str],
) -> list[str]:
    lowered = text.lower()
    main_set = set(main_businesses)
    finance_main_context = (
        "sector: financial" in lowered
        or "financial sector" in lowered
        or "banking" in lowered
        or "asset management" in lowered
        or "銀行" in lowered
        or "証券" in lowered
    )
    auto_manufacturer_context = _company_research_is_auto_manufacturer_context(lowered)
    retail_main_context = _company_research_is_retail_main_context(lowered)
    cloud_infra_context = _company_research_is_cloud_infrastructure_context(lowered)
    filtered = list(businesses)
    if not (
        _company_research_is_materials_chemical_context(lowered)
        or _company_research_is_trading_company_context(lowered)
        or _company_research_is_energy_context(lowered)
        or _company_research_is_utility_energy_context(lowered)
    ):
        filtered = [item for item in filtered if item != "材料・化学"]
    if auto_manufacturer_context:
        filtered = [item for item in filtered if item != "資産運用"]
    if _company_research_is_industrial_conglomerate_context(lowered):
        filtered = [
            item
            for item in filtered
            if item not in {"金融サービス", "リース", "保険", "資産運用", "ソフトウェア"}
        ]
    if _company_research_is_railroad_context(lowered):
        filtered = [
            item
            for item in filtered
            if item not in {"金融サービス", "リース", "保険", "資産運用", "ソフトウェア"}
        ]
    if _company_research_is_heavy_machinery_context(lowered):
        filtered = [item for item in filtered if item not in {"ソフトウェア", "資産運用"}]
    if _company_research_is_consumer_electronics_context(lowered):
        filtered = [item for item in filtered if item not in {"リース", "保険", "資産運用"}]
    if retail_main_context and not cloud_infra_context and not auto_manufacturer_context:
        filtered = [
            item
            for item in filtered
            if item not in {"金融サービス", "リース", "保険", "資産運用", "ソフトウェア"}
        ]
    if _company_research_is_healthcare_context(lowered):
        filtered = [
            item
            for item in filtered
            if item not in {"金融サービス", "リース", "保険", "資産運用", "ソフトウェア"}
        ]
    if _company_research_is_energy_context(lowered):
        filtered = [
            item
            for item in filtered
            if item not in {"金融サービス", "保険", "資産運用", "ソフトウェア"}
        ]
    if _company_research_is_utility_energy_context(lowered):
        filtered = [
            item
            for item in filtered
            if item
            not in {
                "金融サービス",
                "リース",
                "部品・アフターサービス",
                "ソフトウェア",
                "保険",
                "資産運用",
            }
        ]
    if _company_research_is_telecom_context(lowered):
        filtered = [item for item in filtered if item not in {"金融サービス", "保険", "資産運用"}]
    if (
        _company_research_is_software_cloud_context(lowered)
        and not finance_main_context
        and not auto_manufacturer_context
    ):
        filtered = [
            item
            for item in filtered
            if item not in {"金融サービス", "保険", "資産運用", "リース", "ソフトウェア"}
        ]
    if "決済ネットワーク" in main_set:
        filtered = [
            item for item in filtered if item not in {"金融サービス", "資産運用", "ソフトウェア"}
        ]
    if "銀行・金融サービス" in main_set or "金融サービス" in main_set:
        filtered = [item for item in filtered if item != "ソフトウェア"]
    return _unique_text(filtered)[:5]


def _company_research_regions_from_text(text: str) -> list[str]:
    lowered = text.lower()
    specs = (
        ("日本", ("日本", "japan")),
        ("北米", ("北米", "north america", "u.s.", "united states")),
        ("欧州", ("欧州", "europe")),
        ("アジア", ("アジア", "asia")),
        ("グローバル", ("global", "worldwide", "世界")),
    )
    return [label for label, keywords in specs if any(keyword in lowered for keyword in keywords)]


def _company_research_customer_segments(text: str) -> list[str]:
    lowered = text.lower()
    specs = (
        ("個人顧客", ("consumer", "retail", "個人")),
        ("法人顧客", ("corporate", "enterprise", "business customers", "法人")),
        (
            "製造業",
            ("manufacturing", "manufacturers", "factory", "industrial", "製造業"),
        ),
        ("販売店・ディーラー", ("dealer", "dealership", "販売店", "ディーラー")),
        ("フリート顧客", ("fleet", "フリート")),
        ("金融サービス利用者", ("financial services customers", "金融サービス利用者")),
    )
    return [label for label, keywords in specs if any(keyword in lowered for keyword in keywords)]
