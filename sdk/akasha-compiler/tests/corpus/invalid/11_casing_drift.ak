// Expected warning: AKA0113 - class name used in multiple casings.
// Both `Animal` and `animal` are used within this one file.

function void Bad(Animal a) {
    animal other = a;
    Cat c = (Cat) a;
    cat c2 = (cat) a;
}
