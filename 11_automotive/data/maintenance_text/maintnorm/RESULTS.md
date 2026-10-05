# Results

This documentation provides information about the results of our experiments. Our experiments were performed using the MaintNorm model formulation and three baselines (LAI, MFR and UFAL) (see the [Models](./MODELS.md) section for further details). Each model was applied to the hold-out test set and evaluated using precision (P), recall (R) and error reduction rate (E.R.R.) as outlined below. For each model, their performance was assessed on each individual company (with and without extra training data - see [Data](/DATA.md) for more information), and on a combined dataset consisting of all the company data pooled together. The results of these experiments are shown below. We have split them up to ensure visual formatting, but for a more concise view please refer to the [paper](./paper.pdf).

## Evaluation Metrics

To assess the effectiveness of our models, we used precision (P), recall (R), and error reduction rate (E.R.R.), following the methodology outlined in by van der Goot, 2019[^1]. These metrics offer a comprehensive evaluation of test accuracy. Precision measures the accuracy of the normalisation model's replacements, while recall determines the model's ability to identify and correctly normalise anomalies. Together, these metrics complement the E.R.R., addressing its limitations in distinguishing between over-normalisation and under-normalisation. The definitions of precision, recall, and error reduction rate are as follows:


$$
    P = \frac{TP}{TP + FP}
$$

$$
    R = \frac{TP}{TP + FN}
$$

$$
    E.R.R. = \frac{TP - FP}{TP + FN}
$$

Here, the TP (True Positive), FP (False Positive), and FN (False Negative) values are evaluated at the token level. They are conceptualised as follows:

- True Positive (TP): Words that required normalisation and were accurately normalised by the model.
- False Positive (FP): Words incorrectly normalised by the model despite not requiring normalisation.
  False Negative (FN): Words that required normalisation but were either inaccurately normalised or overlooked by the model.

## Experimental Results

### MaintNorm (ours)

| Company | Extra Data | Precision | Recall | Error Reduction Rate |
| :-----: | :--------: | :-------: | :----: | :------------------: |
|    A    |     N      |   99.9    |  95.8  |         95.2         |
|         |     Y      |   99.9    |  98.1  |         96.6         |
|    B    |     N      |   98.9    |  94.6  |         90.0         |
|         |     Y      |   99.7    |  98.1  |         96.6         |
|    C    |     N      |   99.4    |  95.2  |         89.1         |
|         |     Y      |   99.5    |  96.8  |         92.4         |
|  A+B+C  |     -      |   99.7    |  97.5  |         95.8         |



## Leave-As-Is (LAI)

| Company | Extra Data | Precision | Recall | Error Reduction Rate |
| :-----: | :--------: | :-------: | :----: | :------------------: |
|    A    |     N      |     0     |   0    |          0           |
|         |     Y      |     0     |   0    |          0           |
|    B    |     N      |     0     |   0    |          0           |
|         |     Y      |     0     |   0    |          0           |
|    C    |     N      |     0     |   0    |          0           |
|         |     Y      |     0     |   0    |          0           |
|  A+B+C  |     -      |     0     |   0    |          0           |

### Most Frequent Replacement (MFR)

| Company | Extra Data | Precision | Recall | Error Reduction Rate |
| :-----: | :--------: | :-------: | :----: | :------------------: |
|    A    |     N      |   99.9    |  91.7  |         90.9         |
|         |     Y      |   99.9    |  91.7  |         90.9         |
|    B    |     N      |   99.8    |  93.9  |         90.2         |
|         |     Y      |   99.8    |  93.9  |         90.2         |
|    C    |     N      |   99.5    |  89.9  |         78.6         |
|         |     Y      |   99.5    |  89.9  |         78.6         |
|  A+B+C  |     -      |   99.8    |  93.0  |         89.4         |

### UFAL

| Company | Extra Data | Precision | Recall | Error Reduction Rate |
| :-----: | :--------: | :-------: | :----: | :------------------: |
|    A    |     N      |   99.8    |  92.0  |         91.0         |
|         |     Y      |   99.9    |  92.1  |         91.3         |
|    B    |     N      |   99.6    |  91.0  |         85.5         |
|         |     Y      |   99.6    |  91.7  |         86.5         |
|    C    |     N      |   99.4    |  86.6  |         71.9         |
|         |     Y      |   99.1    |  86.6  |         71.5         |
|  A+B+C  |     -      |   99.5    |  90.2  |         85.0         |

**Footnotes**

[^1]: Van Der Goot, Rob. "MoNoise: A multi-lingual and easy-to-use lexical normalization tool." In *Proceedings of the 57th Annual Meeting of the Association for Computational Linguistics: System Demonstrations*, pp. 201-206. 2019.
