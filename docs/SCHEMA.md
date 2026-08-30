# Catalog schema

`data/models.yaml` is the source of truth. One record represents a named model family or a materially distinct model introduced by a paper—not each size or checkpoint in that family.

## Inclusion rule

A model belongs in the catalog when it learns directly from raw DNA or RNA sequence through self-supervised, autoregressive, diffusion, contrastive, or comparable large-scale pre-training and is presented as a reusable representation or generation model. Specialized and multimodal models qualify when nucleotide sequence remains a learned input modality. Model adaptations with a distinct checkpoint and training contribution may also qualify.

The catalog excludes ordinary supervised downstream predictors, systems that only consume embeddings from another nucleotide model, RNA-seq or methylation matrices without raw-sequence pre-training, single-cell expression foundation models, protein-only models, and structure-prediction systems that do not introduce a reusable nucleotide sequence model.

## Controlled fields

- `domain`: `dna`, `rna`, or `dna_rna`.
- `scope`: `general`, `specialized`, `generative`, or `multimodal`.
- `publication_status`: `peer_reviewed`, `preprint`, or `model_release`.
- `first_public_date`: earliest known public model, manuscript, or checkpoint date in `YYYY.MM` format.
- `publication_date`: peer-reviewed publication date when available; otherwise `null`.

## Model fields

Required keys are `name`, `title`, `paper_url`, `first_public_date`, `first_public_url`, `publication_date`, `publication_status`, `domain`, `scope`, `focus`, `code_url`, `weights_url`, `architecture`, `tokenization`, `objective`, `parameters`, `context_length`, `pretraining_data`, and `summary`.

Optional keys:

- `aliases`: other names used for the same model family.
- `notable_claim`: a concise priority or distinguishing claim explicitly supported by the primary source.

Unknown technical values should be YAML `null`, not guessed values or the string `-`.
