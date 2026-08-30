# Contributing

Thank you for helping maintain the nucleotide language-model catalog.

## Before adding a model

An entry should introduce or release a reusable model learned directly from raw DNA or RNA sequence through self-supervised, autoregressive, diffusion, contrastive, or comparable large-scale pre-training. General, specialized, generative and multimodal models are all in scope when nucleotide sequence remains a learned modality.

Please do not add ordinary supervised predictors, expression-matrix or single-cell models, protein-only models, or tools that merely consume an existing nucleotide model. If an item is important but out of scope, document it in `data/excluded.yaml` with a concise reason.

## Metadata workflow

1. Add one record to `data/models.yaml` using the field definitions in `docs/SCHEMA.md`.
2. Use the earliest verifiable public date and URL. Store a later peer-reviewed date separately.
3. Prefer the primary paper, official code repository and official checkpoint collection.
4. Use YAML `null` for unknown facts. Do not guess or use `-` placeholders.
5. Run:

   ```bash
   python generate_paper_list.py
   python scripts/validate_data.py
   ```

6. Commit the YAML record, generated `README.md`, `assets/model_timeline.svg`, and `assets/model_evolution_tree.svg` together.

One entry represents a model family or materially distinct model contribution. Do not create a separate record for every parameter scale or fine-tuned checkpoint.

## Priority claims

Claims such as “first” require explicit support in a primary source and should be written narrowly. The catalog intentionally preserves this verified UltraGen claim:

> UltraGen is the first RNA language model pre-trained on in vitro-synthesized RNA libraries.

## Pull-request checklist

- [ ] The item meets the raw nucleotide-sequence pre-training scope.
- [ ] The model does not duplicate a name, paper, alias or model family already listed.
- [ ] First-public and publication dates are distinguished.
- [ ] Paper, code and checkpoint links are official where possible.
- [ ] Architecture, tokenization, objective, scale, context and corpus are sourced rather than inferred.
- [ ] The generator and validator pass locally.
