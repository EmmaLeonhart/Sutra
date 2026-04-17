/*
 * Sutra VS Code extension.
 *
 * Three responsibilities:
 *   1. Syntax highlighting is handled by the TextMate grammar in
 *      syntaxes/sutra.tmLanguage.json; no code needed here.
 *   2. Diagnostics from the sutrac compiler are run as a child
 *      process and converted into VS Code diagnostics. Uses the
 *      --json output format so we don't have to parse the text form.
 *   3. Completion/hover: a keyword/primitive/builtin completion
 *      provider for quick autocomplete on language-level tokens.
 */

import * as cp from "child_process";
import * as path from "path";
import * as vscode from "vscode";

// ============================================================
// Constants
// ============================================================

const LANGUAGE_ID = "sutra";
const DIAGNOSTIC_SOURCE = "sutra";

const PRIMITIVE_TYPES = [
    "scalar", "vector", "matrix", "tuple", "string", "bool", "fuzzy", "void",
];

const KEYWORDS = [
    "function", "method", "operator", "static", "public", "private",
    "var", "const", "return", "if", "else", "while", "for", "foreach",
    "in", "do", "try", "catch", "this", "true", "false", "new", "implicit",
];

const BUILTINS = [
    "embed", "defuzzy", "unsafeCast", "unsafeOverride",
    "snap", "similarity", "Cosine",
    "Bundle", "Bind", "Blend", "Normalize",
];

const KEYWORD_DOCS: { [key: string]: string } = {
    "function": "Declare a free function. Public static by default. Return type precedes the name.",
    "method": "Declare a method attached to the enclosing object file. Public non-static by default.",
    "operator": "Declare an overloaded operator. Usage: `function operator +(...)`.",
    "var": "Inferred-type mutable binding. Never combine with an explicit type.",
    "const": "Immutable binding. Can be used with or without an explicit type.",
    "defuzzy": "Collapse a fuzzy value into a concrete bool via the recursive is_true algorithm.",
    "embed": "Convert a string into a vector by running it through the embedding model. Real computation, not a cast.",
    "unsafeCast": "Force a value to be reinterpreted as a different type. `unsafeCast<Type>(value)`.",
    "unsafeOverride": "At a call site, override the function's type acceptance without changing the value.",
    "fuzzy": "Fuzzy truth type — a continuous-valued vector that can be collapsed to bool via defuzzy.",
    "bool": "Concrete boolean type. Distinct from fuzzy at compile time even though both are vectors at runtime.",
    "vector": "Hypervector in semantic space. The core Sutra primitive.",
    "scalar": "Plain numeric value. Used for thresholds, loop counters, weights.",
    "matrix": "2D array. Functions are matrices at the substrate level.",
    "tuple": "Grouped values without superposition. Different from bundling.",
};

// ============================================================
// Diagnostic runner
// ============================================================

interface CompilerDiagnostic {
    file: string;
    line: number;
    column: number;
    end_line: number;
    end_column: number;
    level: "error" | "warning" | "info";
    code: string | null;
    message: string;
    hint: string | null;
}

interface CompilerOutput {
    version: string;
    files: Array<{
        file: string;
        diagnostics: CompilerDiagnostic[];
    }>;
}

function getCompilerCommand(): { cmd: string; args: string[] } {
    const config = vscode.workspace.getConfiguration("sutra");
    const cmd = config.get<string>("compilerPath", "python");
    const args = config.get<string[]>("compilerArgs", ["-m", "sutra_compiler"]);
    return { cmd, args };
}

function runCompiler(filePath: string): Promise<CompilerOutput | null> {
    return new Promise((resolve) => {
        const { cmd, args } = getCompilerCommand();
        const fullArgs = [...args, "--json", filePath];
        const proc = cp.spawn(cmd, fullArgs, {
            cwd: path.dirname(filePath),
        });
        let stdout = "";
        let stderr = "";
        proc.stdout.on("data", (chunk) => { stdout += chunk.toString(); });
        proc.stderr.on("data", (chunk) => { stderr += chunk.toString(); });
        proc.on("error", (err) => {
            console.error("sutrac spawn error:", err);
            resolve(null);
        });
        proc.on("close", () => {
            try {
                const parsed = JSON.parse(stdout) as CompilerOutput;
                resolve(parsed);
            } catch (err) {
                console.error("sutrac returned non-JSON:", stdout, stderr);
                resolve(null);
            }
        });
    });
}

function toVSCodeDiagnostic(
    diag: CompilerDiagnostic,
    showCodes: boolean
): vscode.Diagnostic {
    // Compiler positions are 1-based; VS Code is 0-based.
    const start = new vscode.Position(
        Math.max(0, diag.line - 1),
        Math.max(0, diag.column - 1)
    );
    const end = new vscode.Position(
        Math.max(0, diag.end_line - 1),
        Math.max(0, diag.end_column - 1)
    );
    // If start == end, extend by one column so the squiggle is visible.
    const range = start.isEqual(end)
        ? new vscode.Range(start, start.translate(0, 1))
        : new vscode.Range(start, end);

    const severity =
        diag.level === "error"
            ? vscode.DiagnosticSeverity.Error
            : diag.level === "warning"
                ? vscode.DiagnosticSeverity.Warning
                : vscode.DiagnosticSeverity.Information;

    let message = diag.message;
    if (diag.hint) {
        message += `\n  hint: ${diag.hint}`;
    }

    const vsDiag = new vscode.Diagnostic(range, message, severity);
    vsDiag.source = DIAGNOSTIC_SOURCE;
    if (showCodes && diag.code) {
        vsDiag.code = diag.code;
    }
    return vsDiag;
}

async function validateDocument(
    doc: vscode.TextDocument,
    collection: vscode.DiagnosticCollection
) {
    if (doc.languageId !== LANGUAGE_ID) {
        return;
    }
    const output = await runCompiler(doc.uri.fsPath);
    if (output === null) {
        return;
    }
    const config = vscode.workspace.getConfiguration("sutra");
    const showCodes = config.get<boolean>("showDiagnosticCodes", true);
    const diags: vscode.Diagnostic[] = [];
    for (const fileEntry of output.files) {
        for (const d of fileEntry.diagnostics) {
            diags.push(toVSCodeDiagnostic(d, showCodes));
        }
    }
    collection.set(doc.uri, diags);
}

async function validateWorkspace(
    collection: vscode.DiagnosticCollection
) {
    const files = await vscode.workspace.findFiles("**/*.su");
    for (const uri of files) {
        const doc = await vscode.workspace.openTextDocument(uri);
        await validateDocument(doc, collection);
    }
}

// ============================================================
// Completion provider
// ============================================================

function makeKeywordCompletion(
    word: string,
    kind: vscode.CompletionItemKind,
    detail: string
): vscode.CompletionItem {
    const item = new vscode.CompletionItem(word, kind);
    item.detail = detail;
    const doc = KEYWORD_DOCS[word];
    if (doc) {
        item.documentation = new vscode.MarkdownString(doc);
    }
    return item;
}

const completionProvider: vscode.CompletionItemProvider = {
    provideCompletionItems() {
        const items: vscode.CompletionItem[] = [];
        for (const kw of KEYWORDS) {
            items.push(
                makeKeywordCompletion(
                    kw,
                    vscode.CompletionItemKind.Keyword,
                    "Sutra keyword"
                )
            );
        }
        for (const t of PRIMITIVE_TYPES) {
            items.push(
                makeKeywordCompletion(
                    t,
                    vscode.CompletionItemKind.TypeParameter,
                    "Sutra primitive type"
                )
            );
        }
        for (const b of BUILTINS) {
            items.push(
                makeKeywordCompletion(
                    b,
                    vscode.CompletionItemKind.Function,
                    "Sutra built-in"
                )
            );
        }
        return items;
    },
};

// ============================================================
// Activation
// ============================================================

export function activate(context: vscode.ExtensionContext) {
    const diagnostics = vscode.languages.createDiagnosticCollection(LANGUAGE_ID);
    context.subscriptions.push(diagnostics);

    // Validate on open/save/change depending on config.
    context.subscriptions.push(
        vscode.workspace.onDidOpenTextDocument((doc) =>
            validateDocument(doc, diagnostics)
        )
    );
    context.subscriptions.push(
        vscode.workspace.onDidSaveTextDocument((doc) => {
            const config = vscode.workspace.getConfiguration("sutra");
            const mode = config.get<string>("validateOn", "save");
            if (mode === "save" || mode === "change") {
                void validateDocument(doc, diagnostics);
            }
        })
    );
    context.subscriptions.push(
        vscode.workspace.onDidChangeTextDocument((evt) => {
            const config = vscode.workspace.getConfiguration("sutra");
            const mode = config.get<string>("validateOn", "save");
            if (mode === "change") {
                void validateDocument(evt.document, diagnostics);
            }
        })
    );

    // Validate every already-open Sutra document on activation.
    for (const doc of vscode.workspace.textDocuments) {
        void validateDocument(doc, diagnostics);
    }

    // Commands.
    context.subscriptions.push(
        vscode.commands.registerCommand("sutra.validateFile", async () => {
            const editor = vscode.window.activeTextEditor;
            if (editor) {
                await validateDocument(editor.document, diagnostics);
            }
        })
    );
    context.subscriptions.push(
        vscode.commands.registerCommand("sutra.validateWorkspace", async () => {
            await validateWorkspace(diagnostics);
            vscode.window.showInformationMessage(
                "Sutra: validated all .su files in the workspace"
            );
        })
    );

    // Run & Visualize command.
    context.subscriptions.push(
        vscode.commands.registerCommand("sutra.runVisualize", async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor || editor.document.languageId !== LANGUAGE_ID) {
                vscode.window.showWarningMessage("Open a .su file first.");
                return;
            }
            const filePath = editor.document.uri.fsPath;
            const { cmd, args } = getCompilerCommand();
            const fullArgs = [...args, "--run-viz", filePath];

            // Show output channel for program results
            const output = vscode.window.createOutputChannel("Sutra");
            output.show(true);
            output.appendLine(`Running: ${cmd} ${fullArgs.join(" ")}`);

            const proc = cp.spawn(cmd, fullArgs, {
                cwd: path.dirname(filePath),
            });
            let stdout = "";
            let stderr = "";
            proc.stdout.on("data", (chunk) => {
                const text = chunk.toString();
                stdout += text;
                output.append(text);
            });
            proc.stderr.on("data", (chunk) => {
                const text = chunk.toString();
                stderr += text;
                output.append(text);
            });
            proc.on("error", (err) => {
                output.appendLine(`Error: ${err.message}`);
            });
            proc.on("close", (code) => {
                if (code !== 0) {
                    output.appendLine(`\nCompiler exited with code ${code}`);
                    return;
                }
                // Read the trace JSON and open the webview
                const traceJsonPath = filePath.replace(/\.su$/, "_trace.json");
                const fs = require("fs") as typeof import("fs");
                try {
                    const traceData = fs.readFileSync(traceJsonPath, "utf-8");
                    const trace = JSON.parse(traceData);
                    openVisualizerPanel(context, trace, path.basename(filePath));
                } catch (err: any) {
                    output.appendLine(`Could not read trace: ${err.message}`);
                    // Fall back to opening the HTML file in the browser
                    const htmlPath = filePath.replace(/\.su$/, "_viz.html");
                    if (fs.existsSync(htmlPath)) {
                        vscode.env.openExternal(vscode.Uri.file(htmlPath));
                    }
                }
            });
        })
    );

    // Completion provider.
    context.subscriptions.push(
        vscode.languages.registerCompletionItemProvider(
            { scheme: "file", language: LANGUAGE_ID },
            completionProvider,
            // Trigger on any letter so standard word completion works.
            ..."abcdefghijklmnopqrstuvwxyz".split("")
        )
    );
}

// ============================================================
// 3D Visualizer Webview
// ============================================================

function openVisualizerPanel(
    context: vscode.ExtensionContext,
    trace: any,
    programName: string
) {
    const panel = vscode.window.createWebviewPanel(
        "sutraVisualizer",
        `Sutra 3D — ${programName}`,
        vscode.ViewColumn.Beside,
        {
            enableScripts: true,
            retainContextWhenHidden: true,
        }
    );

    // Read the visualizer HTML template
    const fs = require("fs") as typeof import("fs");
    const templatePath = path.join(
        context.extensionPath, "media", "visualizer.html"
    );
    let html = fs.readFileSync(templatePath, "utf-8");

    // Inject trace data before the module script
    const inject = `<script>window.SUTRA_TRACE_DATA = ${JSON.stringify(trace)};</script>`;
    html = html.replace(
        '<script type="module">',
        inject + '\n<script type="module">'
    );

    panel.webview.html = html;
}

export function deactivate() {
    // nothing
}
