// Evaluate a splash script file in a bare VM and print the returned value as a string.
use makepad_script::*;
fn main() {
    let path = std::env::args().nth(1).expect("usage: run_file <script>");
    let code = std::fs::read_to_string(&path).unwrap();
    let host = Box::leak(Box::new(ScriptVmHost::new(0i32, ())));
    let vm = &mut ScriptVm { host, bx: Box::new(ScriptVmBase::new()) };
    let sm = ScriptMod { file: path.clone(), line: 1, column: 1, code, ..Default::default() };
    let v = vm.eval(sm);
    let mut out = String::new();
    if let Some(s) = vm.string_with(v, |_vm, s| s.to_string()) { out = s; } else { out = format!("{:?}", v); }
    println!("{}", out);
    vm.drain_errors();
}
