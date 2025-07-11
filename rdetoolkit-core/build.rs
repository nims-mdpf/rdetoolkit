use std::process::Command;

fn main() {
    // SKIP_BUILD_RS環境変数が"1"の場合、build.rsをスキップ
    if std::env::var("SKIP_BUILD_RS").unwrap_or_default() == "1" {
        return;
    }

    if cfg!(target_os = "windows") {
        // Pythonのバージョン情報を取得
        let version = Command::new("python")
            .arg("-c")
            .arg("import sys; print(f'{sys.version_info.major}{sys.version_info.minor}')")
            .output()
            .expect("Failed to get Python version");

        let version = String::from_utf8(version.stdout)
            .expect("Invalid UTF-8")
            .trim()
            .to_string();

        // Pythonのライブラリパスを取得
        let python_libs = Command::new("python")
            .arg("-c")
            .arg(
                "import sys; from pathlib import Path; print(Path(sys.executable).parent / 'libs')",
            )
            .output()
            .expect("Failed to get Python lib path");

        let python_libs = String::from_utf8(python_libs.stdout)
            .expect("Invalid UTF-8")
            .trim()
            .to_string();

        // インクルードパスを取得
        let python_include = Command::new("python")
            .arg("-c")
            .arg("import sysconfig; print(sysconfig.get_path('include'))")
            .output()
            .expect("Failed to get Python include path");

        let python_include = String::from_utf8(python_include.stdout)
            .expect("Invalid UTF-8")
            .trim()
            .to_string();

        // Windows用の設定
        println!("cargo:rustc-link-search=native={python_libs}");
        println!("cargo:rustc-link-lib=python{version}");
        println!("cargo:include={python_include}");

        // デバッグ情報を出力
        println!("cargo:warning=Python version: {version}");
        println!("cargo:warning=Python libs path: {python_libs}");
        println!("cargo:warning=Python include path: {python_include}");
    } else {
        // Unix系OSの場合
        let python_version_output = Command::new("python3")
            .arg("-c")
            .arg("import sys; print(f'python{sys.version_info.major}.{sys.version_info.minor}')")
            .output()
            .expect("Faild to get Python version");

        let python_version = String::from_utf8(python_version_output.stdout)
            .expect("Invalid UTF-8 sequence")
            .trim()
            .to_string();

        println!("cargo:rustc-link-lib={python_version}");

        let python_include_dir = Command::new("python3")
            .arg("-c")
            .arg("from distutils.sysconfig import get_python_inc; print(get_python_inc())")
            .output()
            .expect("Failed to get Python include directory");

        let python_lib_dir = Command::new("python3")
            .arg("-c")
            .arg("import sysconfig; print(sysconfig.get_config_var('LIBDIR'))")
            .output()
            .expect("Failed to get Python library directory");

        let python_include_dir = String::from_utf8(python_include_dir.stdout)
            .expect("Invalid UTF-8 sequence")
            .trim()
            .to_string();

        let python_lib_dir = String::from_utf8(python_lib_dir.stdout)
            .expect("Invalid UTF-8 sequence")
            .trim()
            .to_string();

        println!("cargo:include={python_include_dir}");
        println!("cargo:rustc-link-search=native={python_lib_dir}");
    }
}
