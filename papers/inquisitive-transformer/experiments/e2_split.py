"""Experiment 2: Split heads -- half positive, half negative alpha.

Question: Does head specialization help?

Half the attention heads get alpha=+X, the other half get alpha=-X.
This tests whether having some heads focus on anomalies while others
focus on the "normal" signal improves overall performance.
"""

from experiments.common import get_base_parser, load_model, run_alpha_sweep, run_temperature_control


def configure_split(model, alpha):
    """Set first half of heads to +alpha, second half to -alpha.

    Since GPT-2 has 12 layers with 12 heads each, we split by layer:
    layers 0-5 get +alpha, layers 6-11 get -alpha.
    """
    n_layers = len(model.model.transformer.h)
    mid = n_layers // 2

    positive_layers = list(range(mid))
    negative_layers = list(range(mid, n_layers))

    model.set_alpha(alpha, layers=positive_layers)
    model.set_alpha(-alpha, layers=negative_layers)


def main():
    parser = get_base_parser("E2: Split heads (half +alpha, half -alpha)")
    args = parser.parse_args()

    model = load_model(args)

    print("\n" + "=" * 60)
    print("EXPERIMENT 2: Split Heads")
    print("First half of layers: +alpha, second half: -alpha")
    print("=" * 60)

    results = run_alpha_sweep(
        model, args.alphas, "e2_split", args.output_dir,
        configure_fn=configure_split,
    )

    if args.temperature_control:
        run_temperature_control(model, args.temperatures, "e2_split", args.output_dir)

    print("\n" + "=" * 60)
    print("E2 SUMMARY")
    print("-" * 40)
    for r in results:
        print(f"  alpha=±{abs(r.alpha):.2f}  accuracy={r.accuracy:.2%}")


if __name__ == "__main__":
    main()
