"""Experiment 1: Uniform alpha across all heads.

Question: Does the perceptiveness effect exist at all?

All attention heads get the same alpha value. We sweep alpha and measure
CVD benchmark accuracy. If perceptiveness matters, positive alpha should
improve anomaly detection accuracy.
"""

from experiments.common import get_base_parser, load_model, run_alpha_sweep, run_temperature_control


def main():
    parser = get_base_parser("E1: Uniform alpha across all heads")
    args = parser.parse_args()

    model = load_model(args)

    print("\n" + "=" * 60)
    print("EXPERIMENT 1: Uniform Alpha")
    print("All heads receive the same alpha value.")
    print("=" * 60)

    results = run_alpha_sweep(model, args.alphas, "e1_uniform", args.output_dir)

    if args.temperature_control:
        run_temperature_control(model, args.temperatures, "e1_uniform", args.output_dir)

    # Print summary
    print("\n" + "=" * 60)
    print("E1 SUMMARY")
    print("-" * 40)
    for r in results:
        print(f"  alpha={r.alpha:+.2f}  accuracy={r.accuracy:.2%}")


if __name__ == "__main__":
    main()
