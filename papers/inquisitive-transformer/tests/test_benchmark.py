"""Unit tests for the CVD benchmark dataset and evaluation harness."""

import pytest
import torch
from transformers import GPT2Config, GPT2LMHeadModel, GPT2Tokenizer

from src.benchmark.cvd_dataset import (
    get_dataset,
    get_dataset_by_category,
    CATEGORIES,
    NUM_ITEMS,
)
from src.benchmark.evaluate import score_choice, evaluate_model, EvalResult
from src.inquisitive_gpt2 import _replace_attention


class TestCVDDataset:
    def test_dataset_not_empty(self):
        dataset = get_dataset()
        assert len(dataset) > 0

    def test_num_items_matches(self):
        assert NUM_ITEMS == len(get_dataset())

    def test_all_categories_present(self):
        dataset = get_dataset()
        found_categories = set(item["category"] for item in dataset)
        assert found_categories == set(CATEGORIES)

    def test_each_category_has_items(self):
        for cat in CATEGORIES:
            items = get_dataset_by_category(cat)
            assert len(items) >= 4, f"Category {cat} has too few items"

    def test_item_structure(self):
        required_keys = {"category", "passage", "question", "choices", "correct", "violation_hint"}
        for item in get_dataset():
            assert required_keys.issubset(item.keys()), f"Missing keys in item: {item['question']}"

    def test_correct_index_valid(self):
        for item in get_dataset():
            assert 0 <= item["correct"] < len(item["choices"]), (
                f"Invalid correct index {item['correct']} for {len(item['choices'])} choices"
            )

    def test_all_items_have_four_choices(self):
        for item in get_dataset():
            assert len(item["choices"]) == 4, f"Item has {len(item['choices'])} choices"

    def test_no_empty_fields(self):
        for item in get_dataset():
            assert item["passage"].strip(), "Empty passage"
            assert item["question"].strip(), "Empty question"
            assert item["violation_hint"].strip(), "Empty violation_hint"
            for choice in item["choices"]:
                assert choice.strip(), "Empty choice"


class TestScoreChoice:
    @pytest.fixture
    def tiny_model(self):
        config = GPT2Config(
            n_embd=64, n_head=4, n_layer=2, n_positions=128,
            vocab_size=50257, attn_implementation="eager",
        )
        model = GPT2LMHeadModel(config)
        model.eval()
        return model

    @pytest.fixture
    def tokenizer(self):
        tok = GPT2Tokenizer.from_pretrained("gpt2")
        tok.pad_token = tok.eos_token
        return tok

    def test_returns_float(self, tiny_model, tokenizer):
        score = score_choice(tiny_model, tokenizer, "Hello world", "goodbye", "cpu")
        assert isinstance(score, float)

    def test_score_is_negative(self, tiny_model, tokenizer):
        """Log-probabilities should be negative."""
        score = score_choice(tiny_model, tokenizer, "The cat sat on the", "mat", "cpu")
        assert score < 0

    def test_different_choices_different_scores(self, tiny_model, tokenizer):
        context = "The capital of France is"
        s1 = score_choice(tiny_model, tokenizer, context, "Paris", "cpu")
        s2 = score_choice(tiny_model, tokenizer, context, "elephant", "cpu")
        assert s1 != s2


class TestEvaluateModel:
    @pytest.fixture
    def tiny_inquisitive_model(self):
        config = GPT2Config(
            n_embd=64, n_head=4, n_layer=2, n_positions=512,
            vocab_size=50257, attn_implementation="eager",
        )
        model = GPT2LMHeadModel(config)
        model = _replace_attention(model)
        model.eval()
        return model

    @pytest.fixture
    def tokenizer(self):
        tok = GPT2Tokenizer.from_pretrained("gpt2")
        tok.pad_token = tok.eos_token
        return tok

    def test_evaluate_returns_eval_result(self, tiny_inquisitive_model, tokenizer):
        result = evaluate_model(
            tiny_inquisitive_model, tokenizer, device="cpu",
            categories=["planted_incongruence"],
        )
        assert isinstance(result, EvalResult)
        assert 0.0 <= result.accuracy <= 1.0
        assert result.num_items > 0

    def test_evaluate_all_categories(self, tiny_inquisitive_model, tokenizer):
        result = evaluate_model(tiny_inquisitive_model, tokenizer, device="cpu")
        assert result.num_items == NUM_ITEMS
        for cat in CATEGORIES:
            assert cat in result.accuracy_by_category


class TestEvalResultSerialization:
    def test_save_and_load(self, tmp_path):
        from src.benchmark.evaluate import save_results, save_summary_csv

        results = [
            EvalResult(
                alpha=0.0, temperature=1.0, accuracy=0.5,
                accuracy_by_category={"planted_incongruence": 0.6},
                num_items=10, item_results=[],
            )
        ]

        json_path = tmp_path / "test.json"
        csv_path = tmp_path / "test.csv"

        save_results(results, json_path)
        save_summary_csv(results, csv_path)

        assert json_path.exists()
        assert csv_path.exists()
