"""Experiment 4: Doubled heads with paired high/low alpha.

Question: Does capacity matter?

This experiment pairs adjacent layers: even layers get +alpha, odd layers
get -alpha. Combined with the split experiment, this tests whether having
more fine-grained alternation (every other layer) provides a benefit over
a coarse split (first half / second half).

Note: True head-doubling would require architectural changes to GPT-2.
Instead, we approximate by using the existing 12 layers with alternating
alpha, which gives a similar effect of paired high/low processing at
each depth level.
"""

from experiments.common import get_base_parser, load_model, run_alpha_sweep, run_temperature_control


def configure_alternating(model, alpha):
    """Even layers get +alpha, odd layers get -alpha."""
    n_layers = len(model.model.transformer.h)
    for i in range(n_layers):
        layer_alpha = alpha if i % 2 == 0 else -alpha
        model.set_alpha(layer_alpha, layers=[i])


def main():
    parser = get_base_parser("E4: Alternating paired alpha (even=+, odd=-)")
    args = parser.parse_args()

    model = load_model(args)

    print("\n" + "=" * 60)
    print("EXPERIMENT 4: Alternating Paired Alpha")
    print("Even layers: +alpha, odd layers: -alpha")
    print("=" * 60)

    results = run_alpha_sweep(
        model, args.alphas, "e4_alternating", args.output_dir,
        configure_fn=configure_alternating,
    )

    if args.temperature_control:
        run_temperature_control(model, args.temperatures, "e4_alternating", args.output_dir)

    print("\n" + "=" * 60)
    print("E4 SUMMARY")
    print("-" * 40)
    for r in results:
        print(f"  alpha=±{abs(r.alpha):.2f}  accuracy={r.accuracy:.2%}")


if __name__ == "__main__":
    main()
