# Corpora Overview for MaintNorm

This documentation provides a detailed overview of the sub-corpora (datasets) used in the training and evaluation of MaintNorm and its baseline comparisons. The focus of this documentation is to offer insights into the composition, structure, and usage of these datasets within the context of MaintNorm's application in heavy mobile equipment (HME) maintenance.

## Dataset Composition

The MaintNorm dataset comprises 12,000 randomly sampled maintenance short texts (MSTs) originating from three prominent Australian mining and mineral processing organisations. These texts are instrumental in understanding the linguistic nuances and technical jargon prevalent in maintenance short texts.

### Annotator and Annotation Guidelines

- **Single Annotator**: The entire dataset has been meticulously annotated by a dedicated annotator.
- **Annotation Guidelines**: The guidelines followed during annotation are comprehensive, ensuring consistency and accuracy. These guidelines, along with the masking scheme employed, are detailed [here](./README.md#2-guidelines-and-masking-scheme).

### Anonymisation and Data Integrity

To maintain confidentiality, sensitive information within the dataset has been substituted with obfuscated mock data. This process was executed programmatically, preserving the semantics of the original texts. For example, `BF079` which is masked as an `<id>` is not the *true* value for this, instead it mocks the original information's semantic structure e.g. two uppercased alphabetical characters followed by three digits. This process is performed for all of the masks used in MaintNorm.

### Dataset Characteristics

- **Case Sensitivity**: It is important to note that the dataset is case sensitive, reflecting the real-world usage of text in HME maintenance.

## Data Directory Structure and Experimentation Correlation

The dataset is structured within the `./data` directory, segregated based on the source company (A, B, C, and combined A+B+C). The table below presents a correlation between the folder names in the `./data` directory and the experiments conducted as part of the MaintNorm study.

### Directory and Experiment Mapping

| Folder Name | Description                                                  |
| ----------- | ------------------------------------------------------------ |
| `company_a` | Dataset from Company A. Used in experiments with and without additional data. |
| `company_b` | Dataset from Company B. Used in experiments with and without additional data. |
| `company_c` | Dataset from Company C. Used in experiments with and without additional data. |
| `combined`  | Combined dataset from Companies A, B, and C. The `training` portion of this dataset is used with `company_a/b/c` to form the "extra data" experiments. |

### Extra Data Experimentation

- **Extra Data Concept**: In some experiments, the training portion of datasets from other companies (not the primary one being experimented on) is used. This approach is referred to as 'using extra data'.
- **Purpose**: The rationale behind using extra data is to enrich the support for lexical normalisation and masking, thereby enhancing the model's robustness and applicability across different corporate contexts.

## Statistics

This section outlines the original corpus statistics, the normalised and masking corpus statistics, and the detailed characteristics of each sub-corpora.

### Original and Processed Corpus Statistics

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

### Detailed Normalisation and Masking Characteristics

The detailed characteristics (transformations, etc) of the corpora post normalisation and masking is outlined in the following table.

|                                   |   A    |   B    |   C    | A+B+C  |
| --------------------------------: | :----: | :----: | :----: | :----: |
|      **Normalisation Operations** |        |        |        |        |
|                Character addition | 3,022  | 4,704  | 2,781  | 10,507 |
|                 Character removal |  191   |  939   |  247   | 1,377  |
|           Character rearrangement |  145   |  118   |  233   |  358   |
|             Character replacement |  209   |  508   |  231   |  950   |
|                   Token expansion |  662   | 2,264  | 1,281  | 4,207  |
|                     Token removal |  194   |   97   |  195   |  486   |
|                       Title cased |   69   |  118   |   97   |  284   |
|              Partial casing added |   8    |   6    |   9    |   23   |
|                All casing removed | 13,826 | 9,214  | 7,098  | 30,138 |
|                  All casing added |   4    |   29   |   36   |   69   |
|                         No change | 1,978  | 7,178  | 10,173 | 19,338 |
| **Normalisation Transformations** |        |        |        |        |
|                               1:1 | 17,898 | 12,233 | 8,694  | 38,825 |
|                               1:N |  662   | 2,264  | 1,281  | 4,207  |
|                               N:1 |  194   |   97   |  195   |  486   |
|                               N:M |   2    |   4    |   2    |   8    |
|                               N:0 |   7    |   15   |   6    |   28   |
|            **Masking Operations** |        |        |        |        |
|                            `<id>` | 4,055  | 3,916  | 1,116  | 9,087  |
|                     `<sensitive>` |   44   |   25   |  155   |  224   |
|                           `<num>` |  573   | 1,349  |  847   | 2,769  |
|                          `<date>` |   9    |   2    |   49   |   60   |

#### Expanded Examples of Operations and Transformations in Text Normalisation

Text normalisation involves various operations and transformations to modify and standardise text data. Here, we provide detailed descriptions and examples for each category.

##### Normalisation Operations

Normalisation operations are fundamental changes to individual characters or tokens in the text. These include:

- **Character Addition**: Adding missing characters for correction.
  - Example: *rp* to *r**e**p**lace***
- **Character Removal**: Removing extraneous characters.
  - Example: *re**e**place* to *replace*
- **Character Rearrangement**: Correcting character order.
  - Example: ***er**place* to *replace*
- **Character Replacement**: Substituting one character for another.
  - Example: ***t**eplace* to ***r**eplace*
- **Token Expansion**: Expanding abbreviations or acronyms.
  - Example: c/o to *change out*
- **Token Removal**: Removing unnecessary tokens.
  - Example: *replace $* to *replace*
- **Title Cased**: Capitalising the first letter of each word.
  - Example: *a-frame* to ***A**-frame*
- **Partial Casing Added**: Adding case to part of a token.
  - Example: *TEco* to *TE**CO***
- **All Casing Removed**: Converting all characters to lower case.
  - Example: *REPLACE* to *replace*
- **All Casing Added**: Converting all characters to upper case.
  - Example: *teco* to ***TECO***
- **No Change**: No modification required.
  - Example: *replace*

##### Normalisation Transformations

Normalisation transformations involve changing the structure of the text, often affecting the number of tokens:

- **`1:1`**: One-to-one transformation, replacing a single token with another single token.
  - Example: *repl* to *replace*
- **`1:N`**: One-to-many transformation, replacing a single token with multiple tokens.
  - Example: *c/o* to *change out*
- **`N:1`**: Many-to-one transformation, consolidating multiple tokens into a single token.
  - Example: *repl ace* to *replace*
- **`N:M`**: Many-to-many transformation, replacing several tokens with a different number of tokens.
  - Example: *c/ outeng* to *change out engine*
- **`N:0`**: Removing tokens without replacement.
  - Example: *$* to *_*

##### Masking Operations

Masking operations involve replacing specific types of information with semantic tags:

- **`<id>`**: Masking identifiers.
  - Example: "*replace ENG01*" to "*replace `<id>`*"
- **`<sensitive>`**: Masking sensitive information.
  - Example: "*John Smith to inspect*" to "*`<sensitive>` to inspect*"
- **`<num>`**: Masking numerical values.
  - Example: "*replace 2 vents*" to "*replace `<num>` vents*"
- **`<date>`**: Masking date information.
  - Example: "*inspection 2nd March*" to "*inspection `<date>`*"
