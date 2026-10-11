"""Extract WPN website content from the 4 October 2026 manuscript originals.

No model fitting or scientific-data generation takes place. Images are copied
byte-for-byte from the DOCX package; their captions and package relationships
are recorded in public/figures/manifest.json. This script only writes the
content, figures, notices, and content provenance files owned by this task.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import posixpath
import re
import struct
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent.parent
MAIN = WORKSPACE / "Main Text_20261004_fn.docx"
SM = WORKSPACE / "SM_20261004_fn.docx"
CODE = WORKSPACE / "【投稿版本】" / "WPN_code"
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

class Manuscript:
    def __init__(self, path: Path):
        self.path = path
        self.sha256 = sha256(path.read_bytes())
        self.zip = ZipFile(path)
        self.doc = ET.fromstring(self.zip.read("word/document.xml"))
        self.paragraphs = self.doc.findall("./w:body/w:p", NS)
        self.text = ["".join(t.text or "" for t in p.findall(".//w:t", NS)).strip()
                     for p in self.paragraphs]
        self.rels = {r.attrib["Id"]: r.attrib["Target"] for r in
                     ET.fromstring(self.zip.read("word/_rels/document.xml.rels"))}

    def extract_figure(self, figure_id: str, heading_pattern: str) -> tuple[dict, dict]:
        indices = [i for i, text in enumerate(self.text) if re.match(heading_pattern, text)]
        if len(indices) != 1:
            raise ValueError(f"{self.path.name} {figure_id}: expected one caption, found {indices}")
        caption_index = indices[0]
        found = []
        image_index = None
        for i in range(caption_index - 1, max(-1, caption_index - 5), -1):
            embeds = self.paragraphs[i].findall(".//a:blip", NS)
            if embeds:
                found = embeds
                image_index = i
                break
        if len(found) != 1:
            raise ValueError(f"{figure_id}: ambiguous image/caption relationship")
        rid = found[0].attrib[f"{{{NS['r']}}}embed"]
        media = posixpath.normpath("word/" + self.rels[rid])
        data = self.zip.read(media)
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError(f"{figure_id}: source is not PNG")
        width, height = struct.unpack(">II", data[16:24])
        caption_indices = [caption_index]
        if caption_index + 1 < len(self.text) and self.text[caption_index + 1]:
            caption_indices.append(caption_index + 1)
        caption = "\n".join(self.text[i] for i in caption_indices)
        url = f"/figures/{figure_id}.png"
        target = ROOT / "public" / url.lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        figure = {"id": figure_id, "title": self.text[caption_index], "url": url, "caption": caption}
        provenance = {
            **figure, "source_document": self.path.name,
            "source_document_sha256": self.sha256, "source_media": media,
            "relationship_id": rid, "image_paragraph_index": image_index,
            "caption_paragraph_indices": caption_indices,
            "paragraph_index_basis": "zero-based direct body paragraphs in word/document.xml",
            "bytes": len(data), "sha256": sha256(data),
            "width": width, "height": height, "transformation": "none; exact original PNG bytes",
        }
        return figure, provenance

def main() -> None:
    main_doc, supplement = Manuscript(MAIN), Manuscript(SM)
    figures, provenance = [], []
    for figure_id, pattern in [
        ("Fig1", r"^Fig\. 1\s*[|.]"), ("Fig2", r"^Fig\. 2\s*[|.]"),
        ("Fig3", r"^Fig\. 3\s*[|.]"), ("Fig4", r"^Fig\. 4\s*[|.]"),
        ("ED1", r"^Extended Data Fig\. 1\s*[|.]"),
        ("ED2", r"^Extended Data Fig\. 2\s*[|.]"),
        ("ED3", r"^Extended Data Fig\. 3\s*[|.]"),
        ("ED4", r"^Extended Data Fig\. 4\s*[|.]"),
        ("ED6", r"^Extended Data Fig\. 6\s*[|.]"),
    ]:
        figure, record = main_doc.extract_figure(figure_id, pattern)
        figures.append(figure)
        provenance.append(record)
    figure, record = supplement.extract_figure("FigS1", r"^Fig\. S1\s*[|.]")
    figures.append(figure)
    provenance.append(record)

    title = main_doc.text[0].removeprefix("Title:").strip()
    authors = main_doc.text[1].removeprefix("Author:").strip()
    affiliations = [text for text in main_doc.text[2:19] if re.match(r"^\d+ ", text)]
    affiliations = [text.split("???", 1)[0].rstrip(" ,;") if "???" in text else text
                    for text in affiliations]
    correspondence = [text for text in main_doc.text[:22] if text.startswith("*Correspondence")]
    if len(affiliations) != 17 or len(correspondence) != 1:
        raise ValueError("Unexpected team layout in latest manuscript")

    descriptions = {
        "introduction": {
            "title": "WPN — Wastewater-based Prioritization of Neurotoxic Chemical Mixtures",
            "paragraphs": [
                "WPN links wastewater occurrence, estimated daily exposure and chemical-specific potency for neurite-outgrowth inhibition to support screening priorities across European cities. The study covers 52 exogenous target chemicals in 117 Global Urban Boundary (GUB) urban areas across 18 European countries. The panel was selected before exposure translation and effect-based ranking.",
                "The framework brings together georeferenced NORMAN monitoring records, observation-preserving reconstruction of missing concentrations, a wastewater-to-daily-exposure model, toxicokinetic parameters and published relative effect potencies. It distinguishes wastewater concentration (WW), estimated daily exposure (DE) and narciclasine-equivalent bioanalytical equivalent concentration (BEQ), so chemical abundance and contribution to the selected endpoint can be compared on their respective scales.",
                "The mean-based wastewater and BEQ top-ten lists share only two chemicals. 1,2-Benzisothiazol-3(2H)-one (BIT) accounts for 92.03% of across-city mean BEQ while ranking twenty-third by mean wastewater concentration. This identifies a candidate for targeted measurement and effect-based validation; it does not establish BIT's contribution to neurological disease.",
                "This website provides queries, comparisons and downloads of existing study results and their supporting figures. It does not train models or run new predictions on uploaded data. The outputs are intended to guide chemical analysis, human biomonitoring and paired chemical–bioassay studies, rather than estimate individual exposure or city-level disease risk.",
            ],
        },
        "ww": {
            "title": "WW — Urban Wastewater Concentrations and Monitoring Coverage",
            "paragraphs": [
                "The WW module presents concentrations of the 52 target chemicals across the 117 study urban areas. Georeferenced wastewater records were harmonized to GUB spatial units through point-in-polygon matching supplemented by documented station-to-city assignments. Repeated records within the same urban area were summarized as chemical-specific medians to form comparable urban concentration profiles.",
                "Concentrations are reported in nanomoles per litre (nM). The completed target panel contains 6,084 urban-area–chemical values. Originally observed concentrations were retained unchanged; estimates were introduced only for combinations that were missing from the observed matrix. Observed and reconstructed values remain distinguishable when inspecting the stored results.",
                "Wastewater signals can arise from human excretion as well as product use, disposal, industrial discharges and other sewer inputs. Monitoring coverage, sampling conditions and sewer processes also affect these signals. An observed urban median is therefore a summary of available wastewater measurements, while a reconstructed value is a model estimate; neither is a direct measurement of residents' absorbed dose.",
                "Use the Data and Figure views to inspect existing chemical and urban-area profiles, their measurement status and the associated study figures. These views query the completed study dataset; selecting a chemical or city does not initiate a new reconstruction or exposure-model run.",
            ],
        },
        "imputation": {
            "title": "Imputation — Observation-preserving Reconstruction and Validation",
            "paragraphs": [
                "Reconstruction was performed on the broader 117-urban-area × 663-chemical matrix before the fixed 52-chemical panel was extracted. The input contained 12,746 observed cells and 64,825 missing combinations, corresponding to 83.57% missingness. Chemicals and urban areas were subject to minimum coverage criteria, and supported chemical co-occurrence information was derived from original sampling events.",
                "A pretrained TabPFN v2.6 regressor was applied sequentially on the log10(nM) scale, using concentrations of other chemicals, missingness indicators and correlation-based chemical features. Predictions were written only to originally missing positions, and observed concentrations were restored after each step. The final stored reconstruction also includes bounded sampling from chemical-specific validation residuals, with scaling factor 0.2, the 25th–75th percentile interval and random seed 42; this perturbation does not alter measured cells.",
                "Ten repeated masking experiments produced 12,750 held-out predictions covering 8,339 distinct observed cells. Pooled performance was R² = 0.783, RMSE = 0.455 and MAE = 0.321 on the log10 concentration scale. Additional analyses examined newly available observations, consistency between A1 and A2 profiles, and removal of observed values. At 75% observation removal, the mean R² was 0.590.",
                "This module presents the existing reconstruction and validation results, including Fig. S1 and Extended Data Fig. 3. Masking tests assess performance under the documented data conditions; residual sampling is not a posterior distribution, and reconstruction sensitivity does not represent uncertainty propagated through the full WW→DE→BEQ sequence. The website does not fit TabPFN or impute new user data.",
            ],
        },
        "rank": {
            "title": "Rank — Chemical Priorities across WW, DE and BEQ",
            "paragraphs": [
                "The Rank module compares the study's stored wastewater, estimated daily exposure and effect-weighted chemical priorities. WW is reported in nM, DE in μmol day⁻¹, and BEQ in μg L⁻¹ narciclasine-EQ. BEQ combines predicted DE with a standardized body mass of 70 kg, single-compartment toxicokinetic assumptions and a chemical-specific relative effect potency for neurite-outgrowth inhibition. The reference compound molecular mass is 307.25 g mol⁻¹.",
                "Mean and Median describe different summaries across the 117 urban areas. Mean rankings use across-city arithmetic means and support the reported mean chemical contribution profiles. Median rankings use across-urban-area medians; the study's rank transitions classify these median ranks as high (1–18), intermediate (19–35) and low (36–52). Mean-based contributions must not be interpreted as median-based ranks or strata.",
                "BIT moves from rank 23 by mean WW and rank 28 by mean DE to rank 1 by mean BEQ, contributing 92.03% of mean total BEQ. Total model-derived BEQ ranges from 7.281 × 10⁻⁶ to 8.515 × 10⁻⁶ μg L⁻¹ narciclasine-EQ across the study urban areas. Excluding BIT from the stored summaries reveals secondary contributors without refitting the preceding models.",
                "The Data and Figure views allow inspection of these existing ranks, chemical contributions and city comparisons. BEQ is an endpoint-specific screening metric, not a measured human blood concentration or a probability of neurological disease. The 42-chemical WPN–HExpPredict comparison in Extended Data Fig. 6 concerns supplementary DeepToxLab-weighted scores and does not independently validate the current neurite-outgrowth BEQ ranking.",
            ],
        },
    }

    notices_dir = ROOT / "public" / "notices"
    notices_dir.mkdir(parents=True, exist_ok=True)
    notice_sources = [
        (CODE / "THIRD_PARTY_NOTICES.md", "THIRD_PARTY_NOTICES.md"),
        (CODE / "licenses" / "TabPFN-2.6-LICENSE.txt", "TabPFN-2.6-LICENSE.txt"),
        (CODE / "provenance" / "third_party_license_source.json", "third_party_license_source.json"),
    ]
    notice_manifest = []
    for source, name in notice_sources:
        data = source.read_bytes()
        (notices_dir / name).write_bytes(data)
        notice_manifest.append({"url": f"/notices/{name}", "source": str(source),
                                "bytes": len(data), "sha256": sha256(data)})
    interface_notice = ("# LCAP interface attribution\n\n"
        "The WPN website interface is a local adaptation of the LCAP interface at "
        "https://www.exposomex.cn/lcap, prepared from its publicly served interface "
        "code and the user-supplied LCAP design materials. LCAP and ExposomeX "
        "remain the credited interface sources. Rights in source interface "
        "materials remain with their respective rights holders.\n\n"
        "This attribution does not imply that LCAP endorses WPN, that WPN has "
        "acquired LCAP authorship, institutional affiliation or website registration, "
        "or that WPN inherits LCAP's licence. No independent blanket licence "
        "or public redistribution permission for those interface materials is "
        "asserted by this notice. WPN manuscript, data and third-party model "
        "materials retain their separately documented sources and terms.\n")
    interface_bytes = interface_notice.encode("utf-8")
    (notices_dir / "LCAP-attribution.md").write_bytes(interface_bytes)
    notice_manifest.append({"url": "/notices/LCAP-attribution.md", "source": "https://www.exposomex.cn/lcap",
                            "source_kind": "locally written interface attribution", "bytes": len(interface_bytes),
                            "sha256": sha256(interface_bytes)})
    (notices_dir / "manifest.json").write_text(json.dumps(notice_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    paper = {
        "title": title,
        "longName": "Wastewater-based Framework for Prioritizing Neurotoxic Chemical Mixtures",
        "team": {"authorsText": authors, "affiliations": affiliations, "correspondence": correspondence},
        "citation": {
            "text": f"Fu, N. et al. {title}.",
            "status": "Manuscript; publication details pending",
        },
        "license": {"paragraphs": [
            "WPN is presented for research inspection of the study's existing screening results. The supplied research-code package has not assigned a blanket software or artwork licence to the authors' materials. No MIT, Apache, Creative Commons or other general reuse licence is granted by this website; retain the applicable source attributions and consult the authors about permissions for reuse.",
            "The website interface is locally adapted from LCAP (https://www.exposomex.cn/lcap), with attribution to LCAP and ExposomeX. Rights in the source interface remain with their respective holders. This adaptation does not imply endorsement or transfer LCAP authorship, institutional affiliation, website registration or its licence to WPN; the manuscript and research materials retain their separate terms.",
            "Wastewater observations originate from NORMAN. Urban geometry and labels derive from the recorded GUB and GeoNames sources. Exposure estimates, chemical descriptors, toxicokinetic parameters and relative effect potencies retain the attributions to the studies and platforms identified in the manuscript and data records, including SEEM3, IFSQSAR, ADMETlab and the neurite-outgrowth literature. FAO and ExposomeX E-BIO exports are reused scientific sources, not new observations collected by this website.",
            "The supplied package identifies Prior Labs TabPFN v2.6 as a third-party model subject to its recorded non-commercial licence, including restrictions concerning model use, outputs, distribution and hosted services. The original licence text and third-party notices are retained with this website. These materials record the supplied licence version and do not assert that academic intent alone clears every form of reuse or public deployment.",
            "The TABPFN-2.6 Model is licensed by Prior Labs GmbH under the TABPFN-2.6 Non-Commercial License. Copyright © Prior Labs GmbH 2026. THE SERVICES ARE PROVIDED FREE OF CHARGE: COMPANY SHALL NOT BE LIABLE FOR DAMAGES RESULTING FROM SLIGHT NEGLIGENCE. LIABILITY FOR GROSS NEGLIGENCE AND INTENTIONAL MISCONDUCT REMAINS UNAFFECTED.",
            "The study authors fitted a WW-to-DE predictor on their training data and added preprocessing and downstream analysis. WPN is not an official or endorsed Prior Labs product, and no claim is made that the base neural weights were fine-tuned. This website displays stored outputs and does not distribute a TabPFN checkpoint or offer live model inference.",
        ]},
        "descriptions": descriptions,
        "figures": figures,
        "sourceVersions": {
            "mainText": {"filename": MAIN.name, "sha256": main_doc.sha256, "version": "2026-10-04"},
            "supplementary": {"filename": SM.name, "sha256": supplement.sha256, "version": "2026-10-04"},
            "researchCode": {"directory": "【投稿版本】/WPN_code", "versionNote": "Package README identifies 25 September 2026 manuscripts; current website prose and figures use the 4 October 2026 DOCX originals."},
            "thirdPartyNotices": notice_manifest,
            "figureManifest": "/figures/manifest.json",
            "extractedOn": "2026-10-05",
        },
        "notes": [
            "Affiliation 15 ends with an unresolved '???' address in the latest manuscript. Only its confirmed institution wording is shown; no city, postal code or country has been invented.",
            "All nine main-text figures are exact PNGs embedded in Main Text_20261004_fn.docx. Fig1 does not use the older WPN_code artwork. FigS1 is extracted from SM_20261004_fn.docx.",
            "The latest manuscript does not embed an Extended Data Fig. 5 image; no replacement has been fabricated.",
            "The original Extended Data Fig. 2 caption states that the first-column NT52 label requires verification against the fixed-panel union. The image and caption are retained faithfully; this issue has not been silently resolved.",
            "The latest main text reports 201 strong positive FAO associations, while the supplied supplementary Fig. S5 caption reports 193. This website does not present Fig. S5 or manufacture a reconciled figure.",
            "Extended Data Fig. 6 compares 42 chemicals using supplementary DeepToxLab-weighted scores; it is separate from the current 52-chemical neurite-outgrowth BEQ panel.",
            "No journal name, DOI, publication year or live repository status has been inferred from manuscript placeholders. The manuscript date is recorded as a version date.",
        ],
    }
    content_dir = ROOT / "src" / "content"
    content_dir.mkdir(parents=True, exist_ok=True)
    platform_copy = content_dir / "platform-copy.json"
    if platform_copy.exists():
        paper.update(json.loads(platform_copy.read_text(encoding="utf-8")))
        paper["descriptionSections"] = {k: v["sections"] for k, v in paper["descriptions"].items()}
    (content_dir / "paper.json").write_text(json.dumps(paper, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "public" / "figures" / "manifest.json").write_text(json.dumps({
        "version": "2026-10-04 manuscript originals", "figures": provenance,
        "extraction": "Direct DOCX image relationships and adjacent original caption paragraphs; no redrawing, rerendering, cropping or compression.",
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    source_lines = [
        "# WPN 内容来源说明", "",
        "## 当前采用的版本", "",
        f"- 正文：`{MAIN.name}`；SHA256：`{main_doc.sha256}`。",
        f"- 补充材料：`{SM.name}`；SHA256：`{supplement.sha256}`。",
        "- 页面文字及图注以 2026 年 10 月 4 日版本为准。WPN_code 包的 README 标注支持 2026 年 9 月 25 日稿件，因此没有用其旧图替代最新版正文图。",
        "- 提取工具：`tools/extract_paper.py`。该工具只提取文档资源与整理模块说明，不训练模型、不生成新的科研结果。", "",
        "## 图与原始图注对应", "",
        "以下图片全部按 DOCX 原始 PNG 字节提取，未压缩、裁切或改绘。完整图注、原图 SHA256、尺寸、文档关系 ID 与段落定位保存在 `public/figures/manifest.json`。段落编号为 `word/document.xml` 直属正文段落的零起始索引，不是页码。", "",
        "| 网站图 | 来源文档 | DOCX 内图片 | 图段落 | 图注段落 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in provenance:
        source_lines.append(f"| {item['id']} | {item['source_document']} | {item['source_media']} | {item['image_paragraph_index']} | {', '.join(map(str,item['caption_paragraph_indices']))} |")
    source_lines += [
        "", "## Description 内容依据", "",
        "每个栏目包含 4 段英文模块说明，属于依据论文整理的网站文案，不冒充论文原句。",
        "- Introduction：正文摘要、Introduction 与 Results；52 化学物、117 城市、18 国，WW→DE→BEQ 逻辑及 BIT 的均值贡献。",
        "- WW：正文 Materials and Method 第 3 节与 Results；GUB 归并、城市化学物中位数、nM 单位、原观测保留与重建值区分。",
        "- Imputation：正文第 3 节、Results 及补充 Section 4；117×663 背景矩阵、12,746 观测/64,825 缺失、10 次遮蔽验证与有限残差扰动。",
        "- Rank：正文第 4 节、Fig. 3–4 和 Extended Data Fig. 4/6；WW、DE、BEQ 单位，Mean 与 Median 排序口径，BIT 排除分析及补充 42 化学物比较的解释边界。",
        "所有说明均将网页定位为已有结果查询与下载；没有描述上传新数据、实时预测或模型训练能力。", "",
        "## Team 与 Citation", "",
        "作者顺序及数字单位标记来自正文作者行；17 条单位按原序保留。第 15 条单位地址的 `???` 未填补，仅展示已确认机构。通信作者与邮箱直接采用正文。",
        "Citation 使用稿件标题、Fu, N. et al. 与 2026 年 10 月 4 日稿件版本日期，状态为 Manuscript; publication details pending。未编造期刊、DOI 或发表年份。", "",
        "## License & Attribution", "",
        "许可说明依据 `【投稿版本】/WPN_code/THIRD_PARTY_NOTICES.md` 及其保存的 TabPFN-2.6 许可证整理，没有照搬 LCAP 的商业许可条款，也没有为 WPN 自行指定 MIT/CC 等总括许可。",
        "`public/notices` 保留三份原始文件：THIRD_PARTY_NOTICES.md、TabPFN-2.6-LICENSE.txt、third_party_license_source.json，并增加 LCAP-attribution.md 记录界面本地适配来源。清单逐项记录来源与哈希；许可证来源记录注明于 2026 年 9 月 26 日保存，网站未将它声称为实时核验的最新法律文本。",
        "界面来源明确注明 https://www.exposomex.cn/lcap，保留 LCAP/ExposomeX 归属和来源方权利；没有声称 WPN 继承其许可、作者身份、机构或备案资格。",
        "Prior Labs 归属声明完整保留。网页仅显示研究中已有结果；未复制模型检查点，也未提供模型托管或实时推理服务。许可归属与未来发布权限仍分别适用，不将本地材料中缺少许可文件理解为不限用途的授权。", "",
        "## 原稿保留事项", "",
    ]
    source_lines += ["- " + note for note in paper["notes"]]
    (ROOT / "内容来源说明.md").write_text("\n".join(source_lines) + "\n", encoding="utf-8")
    main_doc.zip.close()
    supplement.zip.close()
    print(json.dumps({"figures": len(figures), "original_image_bytes": sum(x['bytes'] for x in provenance),
                      "affiliations": len(affiliations), "description_paragraphs": {k:len(v['paragraphs']) for k,v in descriptions.items()},
                      "notices": len(notice_manifest)}, ensure_ascii=False))

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
