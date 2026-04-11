// Expected error: AKA0001 - unterminated block comment.

/* This comment never closes.
function vector Bad() {
    return embed("cat");
}
