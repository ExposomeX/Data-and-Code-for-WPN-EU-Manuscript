// Website prose adapted from Main Text_20261004_BW.docx.
// Scientific sources and equation provenance: .runtime/bw-methods-brief.md.
export default {
  title: 'WPN',
  overview: [
    'WPN (Wastewater-based Framework for Prioritizing Neurotoxic Chemical Mixtures) is a model platform that translates wastewater chemical concentrations into effect-informed chemical priorities. It combines wastewater occurrence, estimated daily exposure, chemical-specific toxicokinetics and relative potency for neurite-outgrowth inhibition. The study applies this framework to 52 exogenous chemicals across eight chemical classes in 117 urban areas from 18 European countries. By expressing their contributions as narciclasine-equivalent bioanalytical equivalent concentrations (BEQs), WPN helps identify chemicals that contribute most to the modelled mixture effect and supports the selection of targets for biomonitoring and experimental assessment.',
    'The framework comprises four connected stages. First, wastewater occurrence and published neurotoxicity evidence define the target chemical panel. Second, georeferenced monitoring records are harmonized to common urban boundaries, and missing concentrations are reconstructed to form comparable chemical profiles. Third, a fitted model translates wastewater concentrations into estimated daily exposure, followed by toxicokinetic and potency weighting to calculate BEQ. Finally, chemical rankings and mixture contributions reveal how priorities change when biological information is incorporated. Figure 1 summarizes this sequence from chemical selection to effect-informed prioritization.',
    'The website follows the same workflow through four modules. Introduction presents the study, methods and reference data. Chemical provides the identities and properties of the 52 supported chemicals. WPN accepts wastewater concentrations in nM for any selection of these chemicals, with example data available to explore the workflow. Rank displays the resulting BEQ priorities and contributions, alongside a separate view of the study results. Its Code option provides the files needed to run the calculation and produce plots locally.'
  ],
  methods: [
    {
      id: 'target-chemicals',
      title: '1. Target chemical selection and biological evidence',
      blocks: [
        {
          type: 'paragraph',
          text: 'The target panel was established by combining wastewater monitoring coverage with published potency evidence for neurite-outgrowth inhibition. The NORMAN wastewater archive contained 1,035 chemicals, of which 663 were observed in at least three study urban areas. A literature-derived inventory comprised 1,554 candidate chemicals; 97 had positive numerical relative effect potency (REP) values for the selected endpoint. Matching these potency-supported chemicals to the eligible wastewater inventory yielded 53 compounds. Excluding the endogenous marker creatinine produced the final panel of 52 exogenous chemicals, before exposure modelling and effect-based ranking.'
        },
        {
          type: 'paragraph',
          text: 'Chemical identities were reconciled using standardized names, synonyms, CAS Registry Numbers and structural identifiers, with InChIKeys and SMILES supporting duplicate resolution. The panel comprises aromatic polar organics, bisphenols, halogenated persistent organics, organophosphorus compounds, per- and polyfluoroalkyl substances, phthalates, non-halogenated small polar organics, and surfactants and quaternary ammonium compounds.'
        },
        {
          type: 'paragraph',
          text: 'Biological associations were characterized with the ExposomeX E-BIO knowledge system. Two complementary network structures linked chemicals to disease-related biology: Exposure–GO–Disease (EGoD) and Exposure–Protein–Protein–Disease (EPPD). Disease-specific coverage was calculated from the deduplicated union of reached GO terms or proteins relative to the corresponding union for all chemicals associated with that disease. These networks describe the biological connections represented by the chemical panel.'
        }
      ]
    },
    {
      id: 'wastewater-reconstruction',
      title: '2. Urban wastewater concentration reconstruction',
      blocks: [
        {
          type: 'paragraph',
          text: 'Georeferenced NORMAN records were assigned to Global Urban Boundary (GUB) urban areas through point-in-polygon matching and documented station-to-city assignments. Repeated records were aggregated as chemical-specific urban medians. Reconstruction used 117 urban areas and 663 chemicals, including 12,746 observed and 64,825 missing cells. Eligibility required at least three retained chemicals per urban area and a supported correlation with another chemical, based on at least five shared original sampling events. Positive mass concentrations were converted to nM and log-transformed:'
        },
        {
          type: 'equation',
          label: 'Concentration conversion',
          tex: String.raw`C_{ij}^{\mathrm{nM}}=\frac{1000\,C_{ij}^{\mu\mathrm{g}\,\mathrm{L}^{-1}}}{MW_i},\qquad Y_{ij}=\log_{10}C_{ij}^{\mathrm{nM}}`
        },
        {
          type: 'paragraph',
          text: 'Here i indexes chemicals, j indexes urban areas, and MW is molecular mass in g/mol. For each target chemical, the 32 best-covered non-target chemicals provided base predictors. Training-row medians filled missing predictor values; paired missingness indicators and the number of observed predictors described data availability. Positive Spearman correlations supplied additional neighbour summaries:'
        },
        {
          type: 'equation',
          label: 'Correlation-neighbour summary',
          tex: String.raw`R_{ij}^{(K)}=\frac{\sum_{k\in N_i^{(K)}}\rho_{ik}\,\widetilde Y_{kj}}{\sum_{k\in N_i^{(K)}}\rho_{ik}},\qquad K\in\{5,10,20\}`
        },
        {
          type: 'paragraph',
          text: 'N denotes the selected positive-correlation neighbours, ρ their Spearman correlations, and the tilde indicates observed or training-median-filled log concentrations. Reference correlations were rebuilt from 40,657 positive NORMAN records representing 1,580 identifiable sampling events; replicate event–chemical records were summarized by their median. Standardized correlation fingerprints were also reduced to a 16-dimensional principal-component embedding. Euclidean distance d defined similarity S, which weighted the closest embedding neighbours M:'
        },
        {
          type: 'equation',
          label: 'Embedding similarity',
          tex: String.raw`S_{ik}=\frac{1}{1+d_{ik}}`
        },
        {
          type: 'equation',
          label: 'Embedding-neighbour summary',
          tex: String.raw`E_{ij}^{(K)}=\frac{\sum_{k\in M_i^{(K)}}S_{ik}\,\widetilde Y_{kj}}{\sum_{k\in M_i^{(K)}}S_{ik}},\qquad K\in\{5,10\}`
        },
        {
          type: 'paragraph',
          text: 'The ten nearest embedding neighbours additionally contributed their filled concentrations, observation indicators and similarities. A pretrained TabPFN v2.6 regressor reconstructed each target sequentially. Chemicals represented in the reference correlation matrix followed its ordering; unmatched chemicals followed in decreasing order of observed coverage. Predictions populated originally missing cells, and measured values were restored after every target fit. Earlier reconstructions could therefore inform subsequent targets while preserving the observations.'
        },
        {
          type: 'paragraph',
          text: 'Ten repeated masking experiments withheld approximately 10% of eligible observations, retaining at least one measured chemical per urban area and two measured urban areas per chemical. Each repeat reran reconstruction and compared predictions with the withheld values, producing 12,750 predictions across 8,339 distinct cells. Pearson correlation, R², RMSE and MAE evaluated agreement on the log10 scale. Validation residuals were defined as:'
        },
        {
          type: 'equation',
          label: 'Validation residual',
          tex: String.raw`\varepsilon_{ij}=Y_{ij}-\widehat Y_{ij}`
        },
        {
          type: 'paragraph',
          text: 'To restore part of the between-city dispersion, residuals from each chemical’s 25th–75th percentile pool were sampled with replacement using seed 42. Chemicals with fewer than five usable residuals received no perturbation. For originally missing cells, the selected residual scaling factor was 0.2:'
        },
        {
          type: 'equation',
          label: 'Residual-adjusted reconstruction',
          tex: String.raw`\widehat Y_{ij}^{*}=\widehat Y_{ij}+\alpha\varepsilon_{ij}^{*},\qquad\alpha=0.2`
        },
        {
          type: 'equation',
          label: 'Return to concentration units',
          tex: String.raw`\widehat C_{ij}^{\mathrm{nM}}=10^{\widehat Y_{ij}^{*}}`
        },
        {
          type: 'paragraph',
          text: 'The completed study matrix retained measured concentrations and supplied reconstructed values for missing combinations. The 52-chemical panel was then extracted for exposure translation and mixture prioritization.'
        }
      ]
    },
    {
      id: 'wastewater-to-exposure',
      title: '3. Wastewater-to-daily-exposure modelling',
      blocks: [
        {
          type: 'paragraph',
          text: 'The WW-to-DE model was developed from an external dataset containing 11,217 region–chemical records for 1,116 substances across 90 countries or regions. Regional observations were summarized as chemical-level medians. Excluding chemicals reported in only one region left 472 chemicals, each forming one independent modelling unit.'
        },
        {
          type: 'paragraph',
          text: 'Four predictors were used: log10 wastewater concentration in µM, an IFSQSAR fish biotransformation half-life descriptor (fhlb), octanol solubility (logSoliquid), and water solubility (logSwliquid). Missing descriptors were imputed with training-set medians, and the three descriptors were standardized using training-set means and standard deviations. The preprocessing can be written as:'
        },
        {
          type: 'equation',
          label: 'Wastewater model input',
          tex: String.raw`x_{1,i}=\log_{10}\!\left(\frac{WW_i^{\mathrm{nM}}}{1000}\right)`
        },
        {
          type: 'equation',
          label: 'Descriptor standardization',
          tex: String.raw`z_{i,r}=\frac{x_{i,r}-\mu_r}{\sigma_r},\qquad r\in\{2,3,4\}`
        },
        {
          type: 'paragraph',
          text: 'The response was log10 daily exposure (DE, µmol/day). Training exposures were obtained from the SEEM3 Total_median estimate in mg/kg/day, using body mass BW = 70 kg and each chemical’s molecular mass MW in g/mol:'
        },
        {
          type: 'equation',
          label: 'Training exposure conversion',
          tex: String.raw`DE_i^{\mathrm{training}}=\frac{1000\,E_i^{\mathrm{SEEM3}}\,\mathrm{BW}}{MW_i}`
        },
        {
          type: 'paragraph',
          text: 'A TabPFNRegressor learned the relationship between the four predictors and log10 DE. Its predictions were back-transformed to the original exposure scale:'
        },
        {
          type: 'equation',
          label: 'Daily exposure prediction',
          tex: String.raw`\widehat{DE}_i=10^{f_{\mathrm{TabPFN}}(x_{1,i},z_{i,2},z_{i,3},z_{i,4})}`
        },
        {
          type: 'paragraph',
          text: 'Model performance was assessed with randomly shuffled tenfold cross-validation at the chemical level. Pooled out-of-fold predictions were evaluated by R², RMSE and MAE on the log10 scale. Permutation importance quantified predictor contributions. A one-at-a-time sensitivity analysis multiplied wastewater concentrations by factors from 0.1 to 10 while holding descriptors fixed. The platform applies the saved model and preprocessing to the concentrations supplied for the supported chemicals.'
        }
      ]
    },
    {
      id: 'beq-and-ranking',
      title: '4. BEQ calculation and chemical prioritization',
      blocks: [
        {
          type: 'paragraph',
          text: 'Estimated daily exposure was translated under a one-compartment steady-input approximation using chemical-specific elimination half-life and steady-state volume of distribution from ADMETlab 3.0. Multiplication by the dimensionless molar REP for neurite-outgrowth inhibition and the molecular mass of narciclasine expressed each chemical’s contribution on a common BEQ scale:'
        },
        {
          type: 'equation',
          label: 'Chemical-specific BEQ',
          tex: String.raw`BEQ_{ij}=\frac{DE_{ij}}{\mathrm{BW}}\,\frac{t_{1/2,i}}{V_{d,i}\ln2}\,MW_{\mathrm{Narc}}\,REP_i`
        },
        {
          type: 'paragraph',
          text: 'DE is measured in µmol/day; BW is 70 kg; t₁/₂ is the elimination half-life in days; and Vd is the volume of distribution in L/kg. Half-life values supplied in hours are divided by 24, and log10 volume-of-distribution values are back-transformed before calculation. MWNarc = 307.25 g/mol converts the molar equivalent to µg/L narciclasine-EQ. The same calculation is applied separately to each chemical.'
        },
        {
          type: 'paragraph',
          text: 'For each study urban area j, the mixture BEQ was obtained by summing the contributions of all 52 target chemicals:'
        },
        {
          type: 'equation',
          label: 'Study mixture BEQ',
          tex: String.raw`BEQ_j^{\mathrm{mixture}}=\sum_{i=1}^{52}BEQ_{ij}`
        },
        {
          type: 'paragraph',
          text: 'Study chemical priorities were summarized using across-urban-area arithmetic means and medians. For a user calculation, S denotes the chemicals with valid submitted concentrations. Only these chemicals contribute to the current mixture total and percentage contributions:'
        },
        {
          type: 'equation',
          label: 'Current mixture BEQ',
          tex: String.raw`BEQ^{\mathrm{mixture}}=\sum_{i\in S}BEQ_i`
        },
        {
          type: 'equation',
          label: 'Chemical contribution',
          tex: String.raw`\mathit{Contribution}_i\;(\%)=100\,\frac{BEQ_i}{\sum_{k\in S}BEQ_k}`
        },
        {
          type: 'paragraph',
          text: 'Chemicals are ordered by decreasing BEQ. The cumulative contribution curve adds their percentage contributions in that order, showing how many chemicals account for a given share of the calculated mixture effect. Rank presents the current calculation and the study results in separate views.'
        }
      ]
    }
  ]
};
