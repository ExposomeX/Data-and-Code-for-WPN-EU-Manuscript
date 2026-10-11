WPN User Guide

Version: 2.1.0 · Windows 10/11 (64-bit) · CPU · Internet connection required for initial installation; fully offline computation thereafter.
WPN calculates neurotoxic bioanalytical equivalents (BEQs) from wastewater concentrations to support research-based chemical prioritization. Users may select any 1–52 chemicals from the panel of 52 target chemicals. Only valid concentrations submitted by the user are included in the calculations. The web interface is in English.
1. Installation and Startup on Another Computer
1. Extract WPN-Windows-CPU.zip completely into a writable directory, such as D:\WPN. Directory paths containing Chinese characters or spaces are supported. Do not launch the application directly from the ZIP archive.
2. Install the 64-bit Windows version of Python 3.12, retaining the Python launcher. Download the Windows installer (64-bit) from the official Python 3.12.10 release page.
3. Keep the computer connected to the internet and double-click 安装运行环境.bat (Install Runtime Environment). The installer creates a .venv directory in the current project folder and installs fixed dependency versions, including the CPU version of PyTorch. Close the installation window after the message Setup complete appears. If installation fails, follow the displayed instructions and retry. The initial installation requires downloading several large dependencies.
4. Double-click 启动网站.vbs (Start Website). The browser will open http://127.0.0.1:4174/. Calculations can begin once the WPN page displays Model ready. Research materials may be browsed while the model is loading.
5. After use, double-click 停止网站.vbs (Stop Website). Closing the browser tab alone does not stop the local server.
Normal operation does not require Node.js, an NVIDIA graphics card, the authors' Anaconda environment, or the original manuscript directory. The model, preprocessors, parameters, web fonts, maps, and research datasets are included in the distribution package. Once installation is complete, browsing the local website and performing calculations do not require an internet connection. Opening external publications or website links still requires internet access.
When transferring WPN to another computer or changing its installation directory, extract the original delivery ZIP and reinstall the runtime environment. Do not copy the .venv directory.
User inputs and the most recent successful results are stored in the current browser and are not transferred with the ZIP package. Download the CSV files beforehand if these records need to be preserved.
2. Four Main Modules
The home icon in the navigation bar returns users to the WPN homepage. The ExposomeX brand link opens the ExposomeX website. Modules provide Description, Data, and Figure tabs, while the Rank module additionally includes Code.
Module	Functions
Introduction	Description introduces the study and methodology; Data provides research concentrations and validation materials; Figure displays research figures.
Chemical	Provides names, CAS numbers, InChIKeys, chemical categories, and detailed identification information for the 52 supported chemicals. Search and CSV download are available.
WPN	Data allows users to enter, preview, and process their own concentration data; Figure displays the concentration distribution of the currently valid inputs.
Rank	My results displays the most recent successful calculation; Study results presents the ranking based on mean BEQs from the frozen research dataset; Data supports result downloads; Code provides the standalone CPU calculation package.
On the Introduction concentration page, the chemical name, CAS number, and InChIKey filters at the top are interconnected and apply to the data table.
The chemical selector for the chart below operates independently and supports searching, clearing selections, and selecting any individual chemical among the 663 chemicals.
The default chart setting, All chemicals (sum), represents the sum of chemical concentrations within each city (nM), not BEQ. Map colors vary with concentration and are accompanied by a color scale and numerical range. Geographic filters apply simultaneously to the table and chart.
Figure numbers follow the order in which figures appear on the current page. As required by the interface design, the homepage and calculation figures in the WPN and Rank modules do not display figure numbers. Original figure identifiers are retained in filenames and source manifests for traceability and maintenance.
3. Data Input, Preview, and Execution
Under WPN → Data, users may choose any of the following three input methods without switching between input modes:
- Add chemicals: Search by chemical name, CAS number, or InChIKey; click Add chemical; and enter the concentration under WW input (nM).
- Upload file: Click Choose file and select an .xlsx, CSV, or TSV file. For Excel files, only the first worksheet is read. Files must be smaller than 5 MB. Older .xls files must first be saved as .xlsx.
- Paste from Excel: Paste two columns containing a chemical identifier and its concentration, then click Preview pasted data.
Click Download template to obtain the input template.
Example input:
Chemical	WW (nM)
BIT	0.5
102-06-7	1.2
Concentrations must be finite positive numbers expressed in nM. Scientific notation is supported.
Only one concentration record should be retained for each chemical. Unrecognized chemicals, nonnumeric values, zero values, and negative values are marked as invalid.
Chemicals not submitted by the user are not assigned default concentrations, are not treated as zero, and are excluded from the calculations.
Example Data and Input Management
Example data loads demonstration concentrations for all 52 target chemicals. These values represent the median final A2 concentrations of each chemical across 117 cities.
When an example concentration is changed, its status is displayed as Modified. Users can click Restore to recover the original value for an individual chemical or Clear inputs to remove all inputs.
The example dataset is optional and is not used to automatically fill missing chemicals in user-submitted data.
Preview and Calculation
Click Preview N rows to inspect all submitted records and their validation statuses.
The preview always displays every input row and does not provide an additional status filter.
Users may click Back to modify the inputs. Clicking Run N valid chemicals calculates BEQs for valid chemicals only. Calculation cannot proceed if no valid rows are available.
After successful calculation, the interface automatically navigates to:
Rank → Figure → My results
Tables scroll within their designated areas, keeping the primary action buttons accessible at the bottom. On narrow screens, full-page scrolling is supported.
Download CSV saves the current input records. A shortcut to the most recent successful results appears below the Preview / Run section.
4. Results, Figures, and Data Export
My Results
My results includes only the chemicals successfully processed in the current calculation, ranked in descending order of BEQ.
The contribution of each chemical is calculated relative to the sum of BEQs for all chemicals included in the current calculation.
Searching for or hiding table rows does not change the original rankings or the denominator used to calculate contributions.
Study Results
Study results presents rankings based on the mean BEQs of the 52 target chemicals across 117 cities in the research dataset.
The following are distinct statistical quantities and must not be used interchangeably:
- Mean BEQ across cities.
- BEQ newly calculated from the median chemical concentration.
- Median of city-specific BEQs.
Result Visualization
The result figure uses:
- Left y-axis: BEQ.
- Right y-axis: Cumulative contribution (0–100%).
Users may switch between Log scale and Linear scale and adjust the visible range using the slider below the chart.
Click Download PNG to export the figure.
The results Data page and exported CSV retain the following five columns:
Column	Description
Rank	Chemical ranking by BEQ
Chemical	Chemical identifier
WW input (nM)	Input wastewater concentration
BEQ (μg/L Narciclasine-EQ)	Narciclasine-equivalent bioanalytical concentration
Contribution (%)	Percentage contribution to total BEQ
For user-generated results, WW input retains the concentrations submitted in the current calculation. For study results, it represents the cross-city mean wastewater concentration.
Table searches restrict the rows included in CSV exports.
DE and Cb are used internally for calculations but are not displayed in the result tables.
Results Persistence and Computational Consistency
Draft inputs, preview records, and the most recent successful results are stored separately in the current browser.
If inputs are modified after a successful calculation, the interface displays Inputs have changed. Previous results are replaced only after a new calculation succeeds.
A failed calculation does not substitute reference study results for newly calculated results.
Both the website and standalone calculation package perform CPU inference using the original saved model without retraining.
Small numerical differences may arise across hardware configurations, processing batches, or comparisons with earlier GPU-generated results. Frozen research results retain their original values and are not recalculated or overwritten when the computing device changes.
5. Standalone CPU Calculation Package
Under Rank → Code, click WPN Code to download the standalone CPU calculation package.
After fully extracting the package, follow the included README.md:
1. Install Python 3.12.
2. Run Setup_WPN.bat with an internet connection for the initial setup.
3. Enter your own concentration values into inputs/concentrations.xlsx.
4. Run Run_WPN.bat to perform the calculation.
CSV or Excel files can also be dragged directly onto Run_WPN.bat to initiate calculations.
Results are saved in separate timestamped directories under results. Each directory contains the results CSV, figures, and input_check.csv.
The blank input template is not automatically populated with example data. The files under examples are intended only for optional demonstration.
The model files and parameters are included in the package, enabling offline calculation after the runtime environment has been installed.
The original model licensing terms are provided in NOTICE.txt and licenses/TabPFN-2.6-model-LICENSE.txt.
6. Files, Scientific Basis, and Data Provenance
6.1 Project Directory Structure
Directory / File	Purpose
api / local_code	Local server, original model and preprocessors, parameters for the 52 chemicals, standalone calculation code, and examples.
dist	Prebuilt website used directly at startup.
src / public	Maintainable source code, original figures, maps, fonts, research datasets, and downloadable resources.
tests / tools	Automated tests and maintenance utilities; not required for normal browsing or calculations.
.venv / .runtime	Runtime environment, server status, and logs generated on the current computer; excluded from the delivery ZIP.
项目配置.json / api/config.json	Website port configuration and project-relative model locations.
6.2 Scientific Sources and Frozen Research Data
The current study text and original figures are based on the October 4, 2026 BW main manuscript and supplementary materials.
Numerical results are based on the September 25, 2026 A2 frozen analysis.
Research dataset overview
117
Cities
18
Countries
663
Background chemicals


Concentration records
Data category	Records
Total city–chemical combinations	77,571
Measured	12,746
Reconstructed	64,825
52-Chemical Target Panel
Data category	Records
City–chemical combinations	6,084
Measured	1,408
Reconstructed	4,676

DE and BEQ are model-derived quantities.
6.3 Chemical Screening and Model Scope
The literature-derived candidate set contains 1,554 chemicals, of which 97 have evidence of positive biological effects.
Intersecting these candidates with the 663 sufficiently monitored background chemicals yields 53 chemicals. After excluding creatinine, 52 target chemicals remain.
The 472 chemicals used for model training constitute a separate dataset.
For three chemicals in the target panel, some original descriptors were missing and were processed using the saved training imputer.
6.4 Frozen Data Files
The original frozen CSV files are located in public/downloads, with corresponding website copies in dist/downloads.
The available files include:
File	Data content
cities-a2.csv	City-level information
chemicals-a2.csv	Chemical information
concentrations-a2.csv	Chemical concentration records
city-metrics-nt52-a2.csv	City-level metrics for the 52-chemical panel
chemical-ranks-nt52-a2.csv	Chemical ranking results
imputation-validation-predictions-a2.csv	Predictions from imputation validation
imputation-validation-summary-a2.csv	Summary of imputation validation
city-beq-totals-nt52-a2.csv	City-level total BEQ values
data-dictionary.md	Data dictionary and variable definitions
The webpage's Download filtered CSV function exports the currently filtered dataset.
6.5 Long-Term Provenance and Licensing Records
The following files are maintained as permanent provenance and licensing records, rather than temporary acceptance-testing reports.
File	Description
src/content/content-provenance.json	Source document hashes, paragraph-to-media relationships, and issues identified in the original manuscript.
src/content/catalog-provenance.json	Sources of chemical identity information and field-level rules.
src/content/catalog-structure-audit.json	Cached structural audit results for the chemical catalog.
public/figures/manifest.json	Sources, original captions, dimensions, and SHA-256 checksums for 15 original embedded PNG figures.
public/data/chemical-catalog.json	Field-level identity provenance, rejected anomalous fields, and missing-data indicators; does not modify frozen research CSV files.
public/data/validation-report.json	Machine-readable verification information for research datasets.
local_code/models/manifest.json	Checksums for the original model and preprocessors.
requirements-tested.txt	Pinned dependency versions used for installation.
public/notices/THIRD_PARTY_NOTICES.md	Third-party notices.
local_code/NOTICE.txt	Model-related notices.
local_code/licenses/TabPFN-2.6-model-LICENSE.txt	Original model licensing terms.
Journal information and DOIs must not be fabricated when no formal publication or DOI is available.
No additional MIT, Creative Commons, or other licenses have been assigned to the authors' materials. The original licensing terms for third-party components and models remain applicable.
6.6 Unresolved Discrepancies in the Original Manuscript
The following discrepancies in the original materials have been intentionally preserved:
- ED5: No corresponding original figure is available.
- FAO strong positive associations: The main text reports 201, whereas the Fig. S5 caption reports 193.
- A2 independent masked cells: The supplementary materials report 8,399, whereas the main text and frozen dataset report 8,339. The website summary adopts 8,339.
- E-BIO screening: Inconsistent wording remains in the original materials.
- ED6: Refers to a historical comparison involving 42 chemicals.
- Fig. 2: The correspondence between panels A/B and the original figure caption still requires author verification.
Original figures must not be silently altered, and these discrepancies must not be interpreted as new scientific conclusions.
FAO associations do not establish dietary sources, and E-BIO associations do not establish disease causality. The platform is not intended for individual-level health risk assessment.
7. Maintenance and Redistribution
Normal use does not require Node.js.
Developers modifying the frontend must install Node.js 24 and run the following command in the project directory:
npm ci


After making changes, rebuild the website using:
npm run build


Alternatively, double-click 重建网站.vbs (Rebuild Website).
Refresh the browser after the build is complete. If backend code has been modified, stop and restart the website.
The build process makes at most two attempts, each with a 60-second timeout. Build status is recorded in .runtime/build-last.json.
7.1 Release Procedure
1. Modify the authoritative source files. Interface text is centralized in src/content/platform-copy.json. Do not modify only generated files that may subsequently be overwritten by the build process.
2. Rebuild the standalone calculation package if its code has changed. Run tools/build_code_package.py using the project's Python environment. This generates the CPU ZIP package and manifest under public/downloads. Existing local inputs and historical results are not overwritten.
3. Rebuild the website. Ensure that the downloadable resources in dist are consistent with those in public.
4. Generate the delivery package. Run tools/build_delivery.py using the project's Python environment. This generates WPN-Windows-CPU.zip and its SHA-256 checksum file in the parent directory of the project. The delivery package excludes machine-specific environments, caches, and user results, and includes a blank input template.
7.2 Testing and Validation
Run Python unit tests using:
.venv\Scripts\python.exe -B -m unittest discover -s tests -p "test_*.py"


Run frontend tests using:
node --test tests/*.test.mjs


Additional tools for testing actual model inference, HTTP functionality, and offline migration are retained under api and tools.
Consult each script's --help output for instructions. Some validation procedures execute the actual model and may require substantial processing time.
Passing unit tests does not establish that the software has been successfully tested on the recipient's computer.
7.3 Data Regeneration
The data preparation tools prepare_catalog.py and prepare_data.py require separate access to the corresponding BW manuscripts, frozen research source files, and training chemical identity sources.
These are not required for normal WPN operation.
extract_paper.py is a retained legacy manuscript extraction tool and must not be used to overwrite the current BW content.
The delivered datasets do not require re-extraction or model retraining.
7.4 Validation Completed for Version 2.1.0
This version has been tested in a newly created CPU environment, including:
- Runtime installation, website startup, and shutdown.
- Actual calculations using 1, 10, and 52 chemicals.
- Actual calculation using one set of frozen city-level inputs.
- Independent execution in directories containing Chinese characters and spaces.
- Validation with external internet access and access to original project resources disabled.
- Verification of webpage resources, data import, and error handling.
These tests were completed on the same computer using independent directories and restricted access conditions.
They do not constitute validation on a separate physical computer. The recipient must still complete the initial installation and perform a test run on their own computer.
8. Troubleshooting
Issue	Recommended action
Python not found	Confirm that 64-bit Python 3.12 and the Python launcher are installed. Advanced users may specify the Python executable directly.
Missing DLL / WinError 126 or 1114	Install the Microsoft Visual C++ v14 Redistributable (x64), then reinstall the runtime environment.
Installation interrupted	Restore internet connectivity and rerun the installation script. Do not copy a runtime environment from another computer.
Preparing model	Allow the model to finish loading; do not repeatedly start the server.
Port already in use	Close the application occupying port 4174 and retry.
Invalid imported data	Review the Status column in the preview for the specific reason.
Website still displays an older version	Refresh the browser, rebuild modified frontend files, or restart the server after backend changes.
Calculation failed	Review the error message and server logs. The most recent successful results remain available.
Python Not Found
Confirm that Python 3.12 (64-bit) and the Python launcher are installed.
For advanced installation with an explicitly specified Python executable, use:
powershell -ExecutionPolicy Bypass -File tools/setup.ps1 -Python "C:\actual\path\python.exe"


Replace the example path with the actual location of python.exe.
Missing DLL / WinError 126 or 1114
Install the Microsoft Visual C++ v14 Redistributable (x64), then reinstall the runtime environment.
See the official Microsoft documentation for further information.
Installation Interrupted
Restore internet connectivity and rerun the installation script.
Do not copy .venv from another computer.
If the existing .venv no longer functions after moving the project, delete only the .venv directory inside the current WPN installation directory and reinstall the environment.
Model Remains in "Preparing Model" Status
Allow the model to complete loading without launching another server instance.
If loading fails, inspect:
.runtime/server-error.log


Port 4174 Is Occupied
If another application is using port 4174, the startup script displays a warning and does not forcibly terminate that application.
Close the application using the port and restart WPN.
Invalid Data Import
Review the Status field in the preview to identify the specific validation problem.
For Excel files, concentrations should preferably be stored as plain numeric values rather than formulas, because cached formula results may be empty.
Website Still Displays an Older Version
Refresh the browser.
If frontend source files have changed, rebuild the website before refreshing.
If backend code has changed, stop and restart the local server.
Calculation Failed
Previously successful results are preserved when a new calculation fails.
Review the error message displayed on the website and inspect:
.runtime/server.log
.runtime/server-error.log


Do not substitute reference study data for the results of a failed user calculation.



# WPN 使用说明

版本：2.1.0 · Windows 10/11 64 位 · CPU · 首次安装联网，安装完成后离线计算。

WPN 根据污水浓度计算神经毒性生物分析当量（BEQ），用于研究优先级筛选。可从 52 种目标物质中选择任意 1–52 种；只计算提交的有效浓度。网页为英文。

## 在另一台电脑安装和启动

1. 将 **WPN-Windows-CPU.zip** 完整解压到可写目录，例如 `D:\WPN`。也支持中文和空格路径。不要在压缩包内直接启动。
2. 安装 **Python 3.12 的 Windows 64 位版本**，保留 Python launcher。可从 [Python 3.12.10 官方页面](https://www.python.org/downloads/release/python-31210/) 下载 **Windows installer (64-bit)**。
3. 保持联网，双击 **安装运行环境.bat**。它在当前目录建立 `.venv`，安装固定版本依赖和 CPU 版 PyTorch。看到 `Setup complete` 后关闭安装窗口。失败时按提示处理后重试；首次安装需要下载较大的依赖。
4. 双击 **启动网站.vbs**，浏览器打开 **http://127.0.0.1:4174/**。WPN 页面显示 **Model ready** 后即可计算；模型加载期间可以浏览研究资料。
5. 使用结束后双击 **停止网站.vbs**。只关闭网页不会停止本地服务。

正常运行不需要 Node.js、NVIDIA 显卡、作者的 Anaconda 环境或原论文文件夹。模型、预处理器、参数、网页字体、地图和研究数据已随包提供。安装完成后，网页浏览与计算无需联网；主动打开外部文献和网站链接仍需网络。

**更换电脑或移动安装目录时，使用交付 ZIP 重新解压并重新安装环境。不要复制 `.venv`。** 输入和最近成功的网页结果保存在该浏览器中，不会随 ZIP 迁移；需要保留时先下载 CSV。

## 四个模块

导航栏的房子图标返回 WPN 首页；ExposomeX 品牌链接打开其网站。各模块通过 Description / Data / Figure 切换，Rank 另有 Code。

| 模块 | 使用方式 |
|---|---|
| Introduction | Description 介绍研究与方法；Data 浏览研究浓度及验证资料；Figure 查看研究图件。 |
| Chemical | 查看 52 种支持物质的名称、CAS、InChIKey、类别及详细身份信息；支持搜索和 CSV 下载。 |
| WPN | Data 录入、预览并运行自己的浓度；Figure 查看当前有效输入的浓度分布。 |
| Rank | My results 查看最近一次成功计算；Study results 查看冻结研究的平均 BEQ 排名；Data 下载结果，Code 下载独立 CPU 计算包。 |

Introduction 浓度页上方的名称、CAS、InChIKey 筛选相互联动，用于表格；下方图表物质选择独立，可搜索、清除和选择全部 663 种中的任意一种。图表默认 **All chemicals (sum)**，表示每个城市各物质浓度的总和（nM），不是 BEQ。地图颜色随浓度变化，并提供色棒及数值范围。地理筛选同时作用于表格和图表。

图号按当前页面顺序展示；首页以及 WPN、Rank 的计算图按当前界面要求不显示 Fig 编号。文件名和来源清单保留原稿图的标识，供维护时溯源。

## 输入、预览和运行

在 WPN → Data 的三列中任选一种方式，无需先切换输入模式：

- **Add chemicals**：按名称、CAS 或 InChIKey 搜索，点击 Add chemical，填写 WW input (nM)。
- **Upload file**：点击 Choose file，选择 `.xlsx`、CSV 或 TSV。Excel 读取第一个工作表；文件须小于 5 MB。旧版 `.xls` 请先另存为 `.xlsx`。
- **Paste from Excel**：粘贴“物质标识＋浓度”两列，点击 Preview pasted data。

可点击 Download template 获取模板。示例格式：

| Chemical | WW (nM) |
|---|---|
| BIT | 0.5 |
| 102-06-7 | 1.2 |

浓度必须为 **nM 单位的有限正数**，支持科学计数法。重复物质须只保留一条浓度；无法识别的物质、非数值、零和负数会标记无效。未提交的物质不补默认值、不作为零、不参与计算。

**Example data** 载入 52 种演示浓度，其值是各物质在 117 个城市的 A2 最终浓度中位数。修改示例值后显示 Modified，可用 Restore 恢复单项原值；Clear inputs 清空输入。示例是可选演示入口，不会自动补齐自己的数据。

点击 **Preview N rows** 查看全部记录及 Status。预览始终展示所有行，不另设状态筛选。可用 Back 返回修改；Run N valid chemicals 只计算有效物质，没有有效行时不能运行。成功后自动进入 Rank → Figure → My results。

表格在自身区域滚动，底部保留主要操作；窄屏允许整页滚动。Download CSV 保存当前输入。最近成功结果的入口位于 Preview / Run 下方。

## 结果、图表和导出

My results 只包含本次成功计算的物质，按 BEQ 从高到低排序。贡献率分母是**本次全部参与物质的 BEQ 总和**。搜索或隐藏行不改变排名及分母。

Study results 使用研究中 52 种物质在 117 个城市的平均 BEQ 排名。平均 BEQ、对中位浓度的新计算和逐城 BEQ 的中位数是不同统计量，不能互相替代。

结果图左轴为 BEQ，右轴为累计贡献率（0–100%）。可切换 Log scale / Linear scale，并用底部滑条改变可见范围。Download PNG 导出图像。结果 Data 页和 Download CSV 保留五列：

**Rank | Chemical | WW input (nM) | BEQ (μg/L Narciclasine-EQ) | Contribution (%)**

自己的结果保留本次输入 WW；研究结果使用跨城市平均 WW。表格搜索会限定 CSV 导出行。DE、Cb 用于内部计算，不在此结果表中展示。

草稿、预览和最近成功结果分别保存在当前浏览器。修改输入后，已有结果提示 Inputs have changed；新计算成功才替换旧结果。失败不会用研究参考结果冒充新结果。

网站和独立计算包均使用原保存模型进行 **CPU 推理，不重新训练**。不同硬件、批次和旧 GPU 结果可有小幅数值差异；冻结研究结果保持原数值，不因切换计算设备而重新改写。

## 独立 CPU 计算包

在 Rank → Code 下载 WPN Code，完整解压后按包内 README.md 操作：安装 Python 3.12，首次联网运行 Setup_WPN.bat；在 inputs/concentrations.xlsx 填入自己的浓度，再运行 Run_WPN.bat。CSV/Excel 也可拖到 Run_WPN.bat 上运行。

结果保存在 results 下的独立时间目录，包含结果 CSV、图表和 input_check.csv。空白模板不会自动填入示例；examples 仅供主动试用。模型文件和参数随包提供，环境装好后可离线计算。原模型许可见包内 NOTICE.txt 及 licenses/TabPFN-2.6-model-LICENSE.txt。

## 文件、科学依据和来源

| 目录 / 文件 | 用途 |
|---|---|
| api / local_code | 本地服务、原模型与预处理器、52 种参数、独立计算代码和示例。 |
| dist | 已构建网页，启动时直接使用。 |
| src / public | 可维护源码、原图、地图、字体、研究数据和下载资源。 |
| tests / tools | 自动化测试与维护工具；正常浏览与计算无需运行。 |
| .venv / .runtime | 当前电脑生成的环境、服务状态和日志；不包含在交付 ZIP。 |
| 项目配置.json / api/config.json | 网站端口及项目内相对模型位置。 |

当前研究文字和原图依据 **2026-10-04 BW 正文及补充材料**，数值依据 **2026-09-25 A2 冻结分析**：117 个城市、18 个国家、663 种背景化学品，共 77,571 条浓度组合；其中 12,746 实测、64,825 重建。52 种目标面板有 6,084 条城市×物质记录，其中 1,408 实测、4,676 重建。DE 和 BEQ 是模型推导量。

文献候选 1,554 种，其中 97 种具有正数效应证据；与充分监测的 663 种背景物质相交为 53，去除肌酐后得到 52 种目标物。472 种模型训练物质是独立集合。目标面板中 3 种物质的部分原始描述符缺失，由保存的训练填补器处理。

原始冻结 CSV 位于 public/downloads，对应网页副本位于 dist/downloads；包括 cities-a2.csv、chemicals-a2.csv、concentrations-a2.csv、city-metrics-nt52-a2.csv、chemical-ranks-nt52-a2.csv、imputation-validation-predictions-a2.csv、imputation-validation-summary-a2.csv、city-beq-totals-nt52-a2.csv 和 data-dictionary.md。页面 Download filtered CSV 导出当前筛选数据。

以下是长期保留的溯源和许可资料，不是临时验收报告：

- src/content/content-provenance.json：原文文件哈希、段落及媒体关系、原稿问题。
- src/content/catalog-provenance.json、catalog-structure-audit.json：身份数据来源、字段规则及结构核查缓存。
- public/figures/manifest.json：15 张原始嵌入 PNG 的来源、原稿图注、尺寸和 SHA-256。
- public/data/chemical-catalog.json：逐字段身份来源、拒绝的异常字段和缺失标记；未改写冻结研究 CSV。
- public/data/validation-report.json：研究数据的可机读核对信息。
- local_code/models/manifest.json：原模型和预处理器的校验值；requirements-tested.txt 固定安装版本。
- public/notices/THIRD_PARTY_NOTICES.md、local_code/NOTICE.txt、local_code/licenses/TabPFN-2.6-model-LICENSE.txt：第三方告知及模型条款。

尚未有正式期刊和 DOI 的信息不应自行补造。没有给作者材料另行赋予 MIT、CC 等许可；第三方及模型原条款继续适用。

原稿尚存差异保留如下：ED5 没有原图；FAO 强正关联正文为 201、FigS5 图注为 193；A2 独立遮蔽单元补充材料为 8,399、正文及冻结数据为 8,339（网页摘要采用 8,339）；E-BIO 筛选措辞存在冲突；ED6 属于历史 42 物质比较；Fig2 的 A/B 面板与原图注对应关系仍需作者核对。不得静默修改原图或把这些差异当成新的科学结论。FAO 关联不证明饮食来源，E-BIO 关联不证明疾病因果；平台不用于输出个体健康风险。

## 维护与重新交付

正常使用无需 Node.js。前端修改者需安装 Node.js 24，在项目目录执行 `npm ci`；修改后运行 `npm run build` 或双击重建网站.vbs。构建完成再刷新；后端修改后停止并重新启动网站。构建最多尝试两次，每次限时 60 秒，状态记录在 .runtime/build-last.json。

发布顺序：

1. 修改权威源文件。界面文字集中在 src/content/platform-copy.json；不要只改随后会被生成器覆盖的产物。
2. 如改动独立代码包，使用项目 Python 执行 `tools/build_code_package.py`，生成 public/downloads 的 CPU ZIP 和 manifest；它不会覆盖本地已填输入或历史结果。
3. 重建网页，使 dist 与 public 的下载资源一致。
4. 用项目 Python 执行 `tools/build_delivery.py`，在项目上一级生成 WPN-Windows-CPU.zip 及 SHA-256 文件。交付包排除本机环境、缓存和用户结果，并放入空白输入模板。

Python 检查：`.venv\Scripts\python.exe -B -m unittest discover -s tests -p "test_*.py"`。前端检查：`node --test tests/*.test.mjs`。实际模型、HTTP 和离线迁移检查工具保留在 api / tools；按各脚本的 `--help` 使用，部分检查会真实运行模型、耗时较长。单元测试通过不等于已经在接收方电脑试运行。

数据再生成工具 prepare_catalog.py / prepare_data.py 需要另行提供相应 BW 文稿、冻结研究源文件和训练身份来源，不属于正常运行依赖。extract_paper.py 是保留的旧稿提取工具，不应用来覆盖当前 BW 内容。已有交付数据无需重新提取或重新训练。

本版已在新建 CPU 环境完成安装、启停、1/10/52 种物质和一组冻结城市输入的真实计算；同机中文及空格独立目录下，禁止外网和原项目资源访问的验证通过，页面资源、导入和错误处理也已核对。此验证不等于另一台实体电脑已实测，接收方仍须完成首次安装和试运行。
## 常见问题

- **没有找到 Python**：确认安装 64 位 Python 3.12 和 launcher；高级用法为 `powershell -ExecutionPolicy Bypass -File tools/setup.ps1 -Python "C:\实际路径\python.exe"`。
- **缺少 DLL / WinError 126 或 1114**：安装 [Microsoft Visual C++ v14 Redistributable（x64）](https://aka.ms/vc14/vc_redist.x64.exe)，然后重新安装环境。参见 [Microsoft 官方说明](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)。
- **安装中断**：恢复网络后重跑安装入口。不要从其他电脑复制环境。移动后的 .venv 不可用时，只删除当前 WPN 目录中的 .venv 后重装。
- **Preparing model**：等待加载，无需重复启动。加载失败时查看 .runtime/server-error.log。
- **端口占用**：4174 端口由其他程序使用时，启动器会提示，不会强行结束该程序。关闭占用程序后重试。
- **导入无效**：在预览 Status 看具体原因。Excel 浓度建议保存为纯数值，避免公式缓存为空。
- **页面还是旧版**：刷新；修改源码后先重建，修改后端后先停止再启动。
- **运行失败**：最近成功结果会保留；查看网页错误提示及 .runtime/server.log、server-error.log。不要用参考数据代替失败的新计算。
