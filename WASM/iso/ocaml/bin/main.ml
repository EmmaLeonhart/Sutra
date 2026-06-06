(* OCaml isomorph of transformer-vm's wasm/reference.py — the deterministic 35-opcode
   stack machine the autoregressive transformer is isomorphic to. Faithful,
   opcode-for-opcode port of the behavioural path (output + instr/token counts).
   OCaml is structurally close to Sutra; this is the stepping stone.

   Usage: main <program.txt> [max_tokens]   (output -> stdout; counts -> stderr) *)

let mask32 = 0xFFFFFFFF
let mem_size = 10 * 1024 * 1024

let to_signed v = if v >= 0x80000000 then v - 0x100000000 else v

(* Split on any run of ASCII whitespace. *)
let split_ws s =
  let n = String.length s in
  let is_ws c = c = ' ' || c = '\n' || c = '\t' || c = '\r' in
  let toks = ref [] and i = ref 0 in
  while !i < n do
    while !i < n && is_ws s.[!i] do incr i done;
    if !i < n then begin
      let start = !i in
      while !i < n && not (is_ws s.[!i]) do incr i done;
      toks := String.sub s start (!i - start) :: !toks
    end
  done;
  List.rev !toks

let read_file path =
  let ic = open_in_bin path in
  let n = in_channel_length ic in
  let s = really_input_string ic n in
  close_in ic;
  s

let hex t = int_of_string ("0x" ^ t)

(* Parse "{ op b0 b1 b2 b3 ... }" + input section -> (program array, input string). *)
let parse_program text =
  let arr = Array.of_list (split_ws text) in
  if Array.length arr = 0 || arr.(0) <> "{" then failwith "program must start with {";
  let last_brace =
    let r = ref (-1) in
    Array.iteri (fun i t -> if t = "}" then r := i) arr;
    if !r < 0 then failwith "no closing }";
    !r
  in
  let prog = ref [] in
  let i = ref 1 in
  while !i < last_brace do
    let op = arr.(!i) in
    let b0 = hex arr.(!i + 1) and b1 = hex arr.(!i + 2)
    and b2 = hex arr.(!i + 3) and b3 = hex arr.(!i + 4) in
    let imm = b0 lor (b1 lsl 8) lor (b2 lsl 16) lor (b3 lsl 24) in
    prog := (op, imm) :: !prog;
    i := !i + 5
  done;
  (* input section: tokens after last "}", drop trailing commit(...) *)
  let input_toks =
    let n = Array.length arr in
    let rec drop k acc = if k >= n then List.rev acc
      else drop (k + 1) (arr.(k) :: acc) in
    let t = drop (last_brace + 1) [] in
    match List.rev t with
    | last :: rest when String.length last >= 7 && String.sub last 0 7 = "commit(" -> List.rev rest
    | _ -> t
  in
  let buf = Buffer.create 16 in
  (try
     List.iter (fun tok ->
       if String.length tok = 1 then Buffer.add_char buf tok.[0]
       else if String.length tok = 2 then begin
         let b = hex tok in
         if b = 0 then raise Exit;
         Buffer.add_char buf (Char.chr b)
       end else raise Exit)
       input_toks
   with Exit -> ());
  (Array.of_list (List.rev !prog), Buffer.contents buf)

let run program input_str max_tokens =
  let mem = Bytes.make mem_size '\000' in
  let input_base =
    if Array.length program > 0 && fst program.(0) = "input_base"
    then Some (snd program.(0)) else None in
  (match input_base with
   | Some base when String.length input_str > 0 ->
     String.iteri (fun i c -> Bytes.set mem (base + i) c) input_str;
     Bytes.set mem (base + String.length input_str) '\000'
   | _ -> ());

  let stack = ref [] in
  let push x = stack := x :: !stack in
  let pop () = match !stack with x :: r -> stack := r; x | [] -> failwith "underflow" in
  let peek () = match !stack with x :: _ -> x | [] -> failwith "empty" in
  let locals = ref (Array.make 256 0) in
  let call_stack = ref [] in
  let pc = ref 0 and instr = ref 0 and tok = ref 0 in
  let out = Buffer.create 256 in
  let memr a = Char.code (Bytes.get mem a) in
  let memw a v = Bytes.set mem a (Char.chr (v land 0xff)) in
  let cmp f = let b = pop () in let a = pop () in push (if f a b then 1 else 0) in
  let cmps f = let b = to_signed (pop ()) in let a = to_signed (pop ()) in
    push (if f a b then 1 else 0) in

  let trace = try Sys.getenv "ISO_TRACE" = "1" with Not_found -> false in
  (try
    while !pc < Array.length program && !tok < max_tokens do
      let (op, imm) = program.(!pc) in
      incr instr;
      if trace then
        Printf.eprintf "i=%d pc=%d op=%s imm=%d top=%s\n" !instr !pc op imm
          (match !stack with x :: _ -> string_of_int x | [] -> "-");
      (match op with
       | "input_base" ->
         let n = if String.length input_str = 0 then 1 else String.length input_str + 1 in
         tok := !tok + n + 1; incr pc
       | "halt" -> tok := !tok + 1; raise Exit
       | "i32.const" -> push imm; tok := !tok + 5; incr pc
       | "local.get" | "global.get" -> push (!locals).(imm); tok := !tok + 5; incr pc
       | "local.set" -> (!locals).(imm) <- (pop () land mask32); tok := !tok + 5; incr pc
       | "global.set" -> (!locals).(imm) <- (pop () land mask32); tok := !tok + 1; incr pc
       | "local.tee" -> (!locals).(imm) <- peek (); tok := !tok + 5; incr pc
       | "drop" -> ignore (pop ()); tok := !tok + 1; incr pc
       | "select" ->
         let c = pop () in let b = pop () in let a = pop () in
         push (if c <> 0 then a else b); tok := !tok + 5; incr pc
       | "i32.add" -> let b = pop () in let a = pop () in push ((a + b) land mask32); tok := !tok + 5; incr pc
       | "i32.sub" -> let b = pop () in let a = pop () in push ((a - b) land mask32); tok := !tok + 5; incr pc
       | "i32.eqz" -> let v = pop () in push (if v = 0 then 1 else 0); tok := !tok + 5; incr pc
       | "i32.eq" -> cmp ( = ); tok := !tok + 5; incr pc
       | "i32.ne" -> cmp ( <> ); tok := !tok + 5; incr pc
       | "i32.lt_u" -> cmp ( < ); tok := !tok + 5; incr pc
       | "i32.gt_u" -> cmp ( > ); tok := !tok + 5; incr pc
       | "i32.le_u" -> cmp ( <= ); tok := !tok + 5; incr pc
       | "i32.ge_u" -> cmp ( >= ); tok := !tok + 5; incr pc
       | "i32.lt_s" -> cmps ( < ); tok := !tok + 5; incr pc
       | "i32.gt_s" -> cmps ( > ); tok := !tok + 5; incr pc
       | "i32.le_s" -> cmps ( <= ); tok := !tok + 5; incr pc
       | "i32.ge_s" -> cmps ( >= ); tok := !tok + 5; incr pc
       | "i32.load" ->
         let a = (pop () + imm) land mask32 in
         push (memr a lor (memr (a+1) lsl 8) lor (memr (a+2) lsl 16) lor (memr (a+3) lsl 24));
         tok := !tok + 5; incr pc
       | "i32.load8_u" -> let a = (pop () + imm) land mask32 in push (memr a); tok := !tok + 5; incr pc
       | "i32.load8_s" ->
         let a = (pop () + imm) land mask32 in let v = memr a in
         push (if v >= 128 then (v - 256) land mask32 else v); tok := !tok + 5; incr pc
       | "i32.load16_u" ->
         let a = (pop () + imm) land mask32 in push (memr a lor (memr (a+1) lsl 8));
         tok := !tok + 5; incr pc
       | "i32.load16_s" ->
         let a = (pop () + imm) land mask32 in let v = memr a lor (memr (a+1) lsl 8) in
         push (if v >= 32768 then (v - 65536) land mask32 else v); tok := !tok + 5; incr pc
       | "i32.store" ->
         let v = pop () in let a = (pop () + imm) land mask32 in
         memw a v; memw (a+1) (v lsr 8); memw (a+2) (v lsr 16); memw (a+3) (v lsr 24);
         tok := !tok + 5; incr pc
       | "i32.store8" -> let v = pop () in let a = (pop () + imm) land mask32 in memw a v; tok := !tok + 2; incr pc
       | "i32.store16" ->
         let v = pop () in let a = (pop () + imm) land mask32 in
         memw a v; memw (a+1) (v lsr 8); tok := !tok + 3; incr pc
       | "br" -> tok := !tok + 6; pc := !pc + 1 + to_signed imm
       | "br_if" ->
         let c = pop () in
         if c <> 0 then (pc := !pc + 1 + to_signed imm; tok := !tok + 6)
         else (incr pc; tok := !tok + 1)
       | "call" ->
         call_stack := (!pc + 1, !locals, imm) :: !call_stack;
         locals := Array.make 256 0;
         tok := !tok + 6; pc := !pc + 1 + to_signed imm
       | "return" ->
         (match !call_stack with
          | (ret_pc, ret_locals, _) :: rest ->
            call_stack := rest; pc := ret_pc; locals := ret_locals; tok := !tok + 6
          | [] -> failwith "return with empty call stack")
       | "output" -> Buffer.add_char out (Char.chr (pop () land 0xff)); tok := !tok + 1; incr pc
       | other -> failwith ("Unknown op: " ^ other))
    done
  with Exit -> ());
  (!instr, !tok, Buffer.contents out)

let () =
  if Array.length Sys.argv < 2 then (prerr_endline "usage: main <program.txt> [max_tokens]"; exit 2);
  let max_tokens = if Array.length Sys.argv >= 3 then int_of_string Sys.argv.(2) else 200_000_000 in
  let text = read_file Sys.argv.(1) in
  let (program, input_str) = parse_program text in
  let (instr, tok, output) = run program input_str max_tokens in
  print_string output;
  Printf.eprintf "instr_count=%d token_count=%d out_len=%d\n" instr tok (String.length output)
