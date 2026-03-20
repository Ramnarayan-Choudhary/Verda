from hypo_gpt.agents.extractor import PaperIntelligenceExtractor


def test_domain_detection_prefers_cv_when_transformer_and_image_present() -> None:
    extractor = PaperIntelligenceExtractor()
    doc = extractor.extract(
        title="Vision Transformer Pruning",
        text=(
            "This paper studies vision transformer pruning for image classification. "
            "Image benchmarks and segmentation tasks are evaluated with ablation."
        ),
    )
    assert doc.domain == "cv"


def test_pruning_paper_does_not_default_to_control_theory_bridge() -> None:
    extractor = PaperIntelligenceExtractor()
    doc = extractor.extract(
        title="ViNNPruner",
        text=(
            "ViNNPruner supports interactive pruning for image classification with ablation and benchmark analysis. "
            "The work studies sparsity and pruning behavior on ImageNet and CIFAR-10."
        ),
    )
    assert doc.domain == "cv"
    assert doc.analogous_domains
    assert doc.analogous_domains[0] != "control theory"
