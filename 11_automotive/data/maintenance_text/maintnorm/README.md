# MaintNorm: A corpus and benchmark model for lexical normalisation and masking of industrial maintenance short text

[![Paper](https://img.shields.io/badge/Paper-View-green?style=flat&logo=adobeacrobatreader)](https://aclanthology.org/2024.wnut-1.7/)

:wave: ​This repository contains the data, models, and code accompanying the paper titled "MaintNorm: A corpus and benchmark model for lexical normalisation and masking of industrial maintenance short text", submitted to [WNUT 2024](http://noisy-text.github.io/2024/).

## Table of Contents

1. [Overview](#1-overview)
2. [Guidelines and Masking Scheme](#2-guidelines-and-masking-scheme)

   1. [Annotation Guidelines](#21-annotation-guidelines)
   2. [Masking Scheme](#22-masking-scheme)

3. [Corpora](#3-corpora)
   1. [Overview](#31-overview)
   2. [Format](#32-format)
   3. [Statistics](#33-statistics)
4. [Models](#4-models)
5. [Results](#5-results)
6. [License](#6-license)
7. [Contributing](#7-contributing)
8. [Contact](#8-contact)

## 1. Overview

Maintenance short texts are invaluable unstructured data sources, serving as a diagnostic and prognostic window into the operational health and status of physical assets. These user-generated texts, created during routine or ad-hoc maintenance activities, offer insights into equipment performance, potential failure points, and maintenance needs. However, the use of information captured in these texts is hindered by inherent challenges: the prevalence of engineering jargon, domain-specific vernacular, random spelling errors without identifiable patterns, and the absence of standard grammatical structures.

To transform these texts into accessible and analysable data, we introduce the MaintNorm dataset, the first resource specifically tailored for the lexical normalisation task of maintenance short texts. Comprising 12,000 examples, this dataset enables the efficient processing and interpretation of these texts. We demonstrate the utility of MaintNorm by training a lexical normalisation model as a sequence-to-sequence learning task with two learning objectives, namely, enhancing the quality of the texts and masking segments to obscure sensitive information to anonymise data. Our benchmark model demonstrates a universal error reduction rate of 95.8%. The [corpora](#3-corpora) and [benchmark outcomes](#5-results) are made available to the public under the MIT license.

## 2. Guidelines and Masking Scheme

The guidelines used for annotation and the masking scheme used for token-level tagging are outlined as follows.

### 2.1 Annotation Guidelines

For the construction of the MaintNorm corpus, we adhered to the following annotation guidelines:

- **Spelling corrections:** Canonical forms are adopted to rectify spelling discrepancies within the corpus, such as omissions, redundancies, or incorrect characters. For example, abbreviations like ‘eng’ are converted to their full form ‘engine’.
- **True casing:** The dataset is standardised using true casing, where inappropriate capitalisation is corrected. For instance, ‘REPLACE ENGINE’ is modified to ‘replace engine’, except for proper nouns that retain capitalisation, e.g., ‘UL123 teleremote’ to ‘UL123 Tele-Remote’. Acronyms are cased according to their standard usage.
- **Abbreviation expansion:** Maintenance text abbreviations are expanded to their full lexical forms to facilitate uniformity and clarity. For instance, ‘c/o’ becomes ‘change out’.
- **Concatenation and tokenisation:** Incorrectly concatenated multi-word expressions are separated (e.g., ‘repair/replace’ to ‘repair / replace’, ‘250hr’ to ‘250 hour’), enhancing the granularity for downstream tasks such as information extraction.

### 2.2 Masking Scheme

The token masking in our corpus is categorised into four semantic classes:

- `<id>`: Asset identifiers, for example, _ENG001_, _rd1286_
- `<sensitive>`: Sensitive information specific to organisations, including proprietary systems, third-party contractors, and names of personnel.
- `<num>`: Numerical entities, such as _8_, _7001223_
- `<date>`: Representations of dates, either in numerical form like _10/10/2023_ or phrase form such as _8th Dec_

## 3. Corpora

### 3.1. Overview

The MaintNorm corpora comprise seven distinct sub-corpora. These are categorised as follows: (1-3) individual corpora for each of the three companies, developed without supplementary training data; (4-6) separate corpora for each company, each enhanced with additional training data; and (7) a comprehensive, combined corpus. Detailed descriptions and statistical analyses of each corpus are presented in the [Data](./DATA.md) section.

### 3.2 Format

All corpora are formatted in the standard normalisation format used in the WNUT shared tasks. An example item is shown below.

```
XH531	<id>
M/SITE	minesite
GLASS	glass
CUT	cut
&	and
SUPPLY	supply
WINDOW	window
```

### 3.3 Statistics

The following table provides a summary of the MaintNorm corpus statistics. This table displays statistics for 4,000 texts from each company, focusing on heavy mobile equipment. It includes token-based text length and vocabulary size. Changes due to normalisation and masking are indicated by arrows and percentages (↑/↓ X%). The right-hand section of the table delineates the text transformations, categorising them as _Modified_ for texts undergoing normalisation or masking, _Norm Only_ for texts exclusively normalised, and _Mask Only_ for texts solely subjected to masking.

| Company | Length           | Vocab Size   | Tokens        | Modified | Norm Only | Mask Only |
| ------- | ---------------- | ------------ | ------------- | -------- | --------- | --------- |
| A       | 5.2 (1.2)        | 2,561        | 20,944        | -        | -         | -         |
|         | 5.4 (1.3) (+3%)  | 1,106 (-57%) | 21,591 (+3%)  | 3,998    | 115       | 45        |
| B       | 5.5 (1.4)        | 3,100        | 21,919        | -        | -         | -         |
|         | 6.2 (1.8) (+13%) | 1,360 (-56%) | 24,690 (+13%) | 3,946    | 192       | 321       |
| C       | 5.1 (1.5)        | 4,168        | 20,559        | -        | -         | -         |
|         | 5.5 (1.8) (+7%)  | 2,048 (-51%) | 22,114 (+7%)  | 3,431    | 1,879     | 150       |
| A+B+C   | 5.3 (1.4)        | 7,612        | 63,422        | -        | -         | -         |
|         | 5.7 (1.7) (+8%)  | 2,872 (-62%) | 68,395 (+8%)  | 11,375   | 2,116     | 586       |

## 4. Models

We've conducted experiments using sequence-to-sequence Transformer-based models to enable automatic lexical normalisation and masking of maintenance short texts. For comprehensive details about the models, their training methodologies, and steps to reproduce our experiments, kindly refer to the [Models](./MODELS.md) section in this repository.

## 5. Results

The detailed results of the sequence-to-sequence models are provided in the [Results](./RESULTS.md) section. It includes precision, recall and error reduction rate evaluation metrics. These results are crucial in understanding the performance of the models in the normalisation of lexical errors and masking of semantic tokens in a given text corpus.

## 6. License

This project is protected under the MIT License. For detailed licensing information, check out the [LICENSE](./LICENSE.md) file.

## 7. Contributing

Feedback and contributions are always appreciated. If you encounter any discrepancies in the corpora or see opportunities for model enhancement, please don't hesitate to submit a pull request for our evaluation. Additionally, should you have any questions or need clarifications about the contents of this repository, do reach out to us.

## 8. Contact

For any specific inquiries or discussions, kindly get in touch:

- tyler.bikaun@research.uwa.edu.au

## 9. Attribution

If you find this work useful, please cite us 🤗:

```
@inproceedings{bikaun-etal-2024-maintnorm,
    title = "{M}aint{N}orm: A corpus and benchmark model for lexical normalisation and masking of industrial maintenance short text",
    author = "Bikaun, Tyler  and
      Hodkiewicz, Melinda  and
      Liu, Wei",
    editor = {van der Goot, Rob  and
      Bak, JinYeong  and
      M{\"u}ller-Eberstein, Max  and
      Xu, Wei  and
      Ritter, Alan  and
      Baldwin, Tim},
    booktitle = "Proceedings of the Ninth Workshop on Noisy and User-generated Text (W-NUT 2024)",
    month = mar,
    year = "2024",
    address = "San {\.G}iljan, Malta",
    publisher = "Association for Computational Linguistics",
    url = "https://aclanthology.org/2024.wnut-1.7",
    pages = "68--78"
}
```
