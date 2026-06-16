// button_spec.ts — the trainable button's render math, authored in TypeScript and
// transpiled to Sutra (`.su`) by sutra-from-ts (queue B5). This is the concrete
// "linked to the JS stuff" tie-in: the GUI/browser layer is TypeScript/JavaScript, and
// the same button render that the substrate twin (button_frame.su, B1) computes is
// expressed here in TS and lowered to a Sutra program by the TS frontend.
//
// The button is a quartic-SQUIRCLE (rounded rectangle): `inside` is ~1 at the centre,
// >0 inside the squircle, <0 outside; one colour channel composites the page-background
// colour and the button-fill colour by that mask. Pure arithmetic (no division — the
// caller passes inverse half-extents invW/invH), so it lowers cleanly to Sutra's
// elementwise tensor ops, matching button_frame.su's `button_channel`.
//
// (Note: sutra-from-ts currently lowers TS `number` to Sutra `int`; the float-fidelity
// render path is the hand-written button_frame.su used by the optimizer. This TS spec
// demonstrates the JS→Sutra lowering of the button render, and transpiles + compiles.)
function buttonChannel(x: number, y: number, cx: number, cy: number,
                       invW: number, invH: number, page: number, fill: number): number {
    const dx = x - cx;
    const dy = y - cy;
    const sx = dx * invW;
    const sy = dy * invH;
    const sx2 = sx * sx;
    const sy2 = sy * sy;
    const inside = 1 - (sx2 * sx2 + sy2 * sy2);
    return page - page * inside + fill * inside;
}

function main(): number {
    // Centred button, page = 0, fill = 1 → the centre channel is lit (= 1).
    return buttonChannel(0, 0, 0, 0, 1, 1, 0, 1);
}
