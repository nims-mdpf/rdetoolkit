use pyo3::exceptions::{PyFileNotFoundError, PyIOError, PyPermissionError, PyValueError};
use pyo3::prelude::*;
use pyo3::PyErr;
use std::fs;
use std::io::{Error as IoError, ErrorKind};
use std::path::{Path, PathBuf};

fn map_io_err(e: &IoError, context: &str, path: &Path) -> PyErr {
    #[cfg(debug_assertions)]
    eprintln!(
        "[DEBUG] I/O error: {}: path={}. error={}",
        context,
        path.display(),
        e,
    );

    match e.kind() {
        ErrorKind::NotFound => PyFileNotFoundError::new_err(format!(
            "{} failed: File or directory not found: {}",
            context,
            path.display(),
        )),
        ErrorKind::PermissionDenied => {
            PyPermissionError::new_err(format!("{context} failed: Permission denied."))
        }
        _ => PyIOError::new_err(format!("{context} failed: An I/O error occurred.",)),
    }
}

/// A directory manager that handles index-based subdirectories.
///
/// This class manages a directory structure that can include indexed subdirectories
/// under a "divided" folder. The directory path is constructed as:
///
/// - For `idx=0`: `{base_dir}/{dirname}`
/// - For `idx>0`: `{base_dir}/divided/{idx:0{n_digit}d}/{dirname}`
///
/// ```
#[pyclass(module = "rdetoolkit.core")]
#[derive(Clone)]
pub struct ManagedDirectory {
    base_dir: PathBuf,
    dirname: String,
    n_digit: usize,
    #[pyo3(get, set)]
    idx: i32,
    path: PathBuf,
}

#[pymethods]
impl ManagedDirectory {
    /// Create a new `ManagedDirectory`.
    ///
    /// # Arguments
    /// - `base_dir`: The base directory path.
    /// - `dirname`: The directory name to manage.
    /// - `n_digit`: The number of digits for formatting the index (default is 4).
    /// - `idx`: The initial index (default is 0).
    ///
    /// # Returns
    /// A new `ManagedDirectory` instance.
    ///
    /// # Errors
    /// Returns an error if any I/O error occurs while resolving paths.
    #[new]
    #[pyo3(signature = (base_dir, dirname, n_digit=None, idx=None))]
    fn new(
        base_dir: &str,
        dirname: &str,
        n_digit: Option<usize>,
        idx: Option<i32>,
    ) -> PyResult<Self> {
        let n_digit = n_digit.unwrap_or(4);
        let idx = idx.unwrap_or(0);
        let base_dir = PathBuf::from(base_dir);

        if dirname.is_empty() {
            return Err(PyValueError::new_err("Directory name must not be empty"));
        }
        let path = if idx == 0 {
            base_dir.join(dirname)
        } else {
            let divided_dir =
                base_dir
                    .join("divided")
                    .join(format!("{idx:0n_digit$}"));
            divided_dir.join(dirname)
        };

        // fs::create_dir_all(&path).map_err(|e| map_io_err(&e, "create_dir_all", &path))?;

        Ok(ManagedDirectory {
            base_dir,
            dirname: dirname.to_string(),
            n_digit,
            idx,
            path,
        })
    }

    /// Get the full path of the managed directory without creating it.
    ///
    /// # Returns
    /// A string representing the full path to this directory.
    ///
    /// # Errors
    /// No errors will be raised here; this is purely a getter.
    #[getter]
    fn get_path(&self) -> PyResult<String> {
        // fs::create_dir_all(&self.path).map_err(|e| map_io_err(&e, "create_dir_all", &self.path))?;
        Ok(self.path.to_string_lossy().to_string())
    }

    /// Create the managed directory if it doesn't exist.
    ///
    /// # Errors
    /// Returns an error if directory creation fails.
    fn create(&self) -> PyResult<()> {
        fs::create_dir_all(&self.path).map_err(|e| map_io_err(&e, "create_dir_all", &self.path))?;
        Ok(())
    }

    /// List all files and directories in the managed directory.
    ///
    /// # Returns
    /// A list of strings representing file and directory paths inside this directory.
    ///
    /// # Errors
    /// Returns an error if the directory does not exist or if reading the directory fails.
    fn list(&self) -> PyResult<Vec<String>> {
        if !self.path.exists() {
            return Err(PyFileNotFoundError::new_err(format!(
                "Directory does not exist: {}",
                self.path.display(),
            )));
        }
        let entries =
            fs::read_dir(&self.path).map_err(|e| map_io_err(&e, "read_dir", &self.path))?;

        let mut result = Vec::new();
        for entry in entries {
            let entry = entry.map_err(|e2| map_io_err(&e2, "read_dir -> entry", &self.path))?;
            result.push(entry.path().to_string_lossy().to_string());
        }
        Ok(result)
    }

    /// Create a new `ManagedDirectory` instance with the specified index value.
    ///
    /// # Arguments
    /// - `idx`: The index for the new directory (`0` means create under `base_dir`, `>0` under `divided`).
    ///
    /// # Returns
    /// A new `ManagedDirectory` pointing to the indexed path.
    ///
    /// # Errors
    /// - `ValueError`: If `idx` is negative.
    /// - `OSError`: If directory creation fails.
    #[pyo3(signature = (idx))]
    fn __call__(&self, idx: i32) -> PyResult<Self> {
        if idx < 0 {
            return Err(PyValueError::new_err("Index must be non-negative"));
        }

        let path = if idx == 0 {
            self.base_dir.join(&self.dirname)
        } else {
            self.base_dir
                .join("divided")
                .join(format!("{:0width$}", idx, width = self.n_digit))
                .join(&self.dirname)
        };

        fs::create_dir_all(&path).map_err(|e| map_io_err(&e, "create_dir_all (call)", &path))?;

        Ok(Self {
            base_dir: self.base_dir.clone(),
            dirname: self.dirname.clone(),
            n_digit: self.n_digit,
            idx,
            path,
        })
    }

    fn __str__(&self) -> String {
        self.path.to_string_lossy().to_string()
    }

    fn __repr__(&self) -> String {
        format!("ManagedDirectory(path={})", self.path.display())
    }
}

// Utility class for managing multiple directories with support for indexed subdirectories.
///
/// This class provides functionality to:
/// - Create and manage base directories
/// - Create indexed subdirectories under a "divided" folder
/// - Access directories via attribute-style notation
#[pyclass(module = "rdetoolkit.core")]
#[derive(Clone)]
pub struct DirectoryOps {
    base_dir: PathBuf,
    n_digit: usize,
}

#[pymethods]
impl DirectoryOps {
    /// Create a new `DirectoryOps` instance.
    ///
    /// # Arguments
    /// - `base_dir`: Base directory path.
    /// - `n_digit`: Number of digits for formatting indices (default is 4).
    ///
    /// # Returns
    /// A `DirectoryOps` instance for managing the specified base directory.
    ///
    /// # Errors
    /// Returns an error if the base directory is invalid or any I/O operation fails.
    #[new]
    #[pyo3(signature = (base_dir, n_digit=None))]
    fn new(base_dir: &str, n_digit: Option<usize>) -> PyResult<Self> {
        let n_digit = n_digit.unwrap_or(4);
        let base_dir = PathBuf::from(base_dir);

        fs::create_dir_all(&base_dir)
            .map_err(|e| map_io_err(&e, "create_dir_all (base_dir)", &base_dir))?;

        Ok(DirectoryOps { base_dir, n_digit })
    }

    /// Create a `ManagedDirectory` instance for the given directory name without creating it immediately.
    ///
    /// # Arguments
    /// - `name`: The directory name to manage.
    ///
    /// # Returns
    /// A `ManagedDirectory` instance.
    ///
    /// # Errors
    /// No directory is created here, so no I/O error is raised unless path conversion fails.
    fn __getattr__(&self, name: &str) -> PyResult<ManagedDirectory> {
        let path = self.base_dir.join(name);

        // fs::create_dir_all(&path).map_err(|e| map_io_err(&e, "create_dir_all(subdir)", &path))?;

        Ok(ManagedDirectory {
            base_dir: self.base_dir.clone(),
            dirname: name.to_string(),
            n_digit: self.n_digit,
            idx: 0,
            path,
        })
    }

    /// Create all supported directories and optionally their indexed subdirectories.
    ///
    /// When `idx` is specified, creates indexed subdirectories under the "divided" folder
    /// for each supported directory.
    ///
    /// # Arguments
    /// - `idx`: Optional index specifying how many subdirectories to create.
    ///
    /// # Returns
    /// A list of created directory paths as strings.
    ///
    /// # Errors
    /// Returns an error if any directory creation fails.
    #[pyo3(signature = (idx=None))]
    fn all(&self, idx: Option<i32>) -> PyResult<Vec<String>> {
        let base_only_dirs = ["invoice", "invoice_patch", "attachment", "tasksupport"];
        let divided_supported_dirs = vec![
            "structured",
            "meta",
            "thumbnail",
            "main_image",
            "other_image",
            "nonshared_raw",
            "raw",
        ];

        let mut result = Vec::new();

        for dirname in base_only_dirs.iter().chain(divided_supported_dirs.iter()) {
            let path = self.base_dir.join(dirname);
            fs::create_dir_all(&path)
                .map_err(|e| map_io_err(&e, "create_dir_all (base_dirs)", &path))?;
            result.push(path.to_string_lossy().into_owned());
        }

        if let Some(max_idx) = idx {
            if max_idx < 0 {
                return Err(PyValueError::new_err("Index must be non-negative"));
            }
            for i in 1..=max_idx {
                for dirname in &divided_supported_dirs {
                    let mdir = ManagedDirectory::new(
                        self.base_dir.to_str().unwrap(),
                        dirname,
                        Some(self.n_digit),
                        Some(i),
                    )?;
                    fs::create_dir_all(&mdir.path)
                        .map_err(|e| map_io_err(&e, "create_dir_all(divided_dirs)", &mdir.path))?;
                    result.push(mdir.path.to_string_lossy().into_owned());
                }
            }
        }

        Ok(result)
    }

    fn __repr__(&self) -> String {
        format!(
            "DirectoryOps(base_dir={}, n_digit={})",
            self.base_dir.display(),
            self.n_digit
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use pyo3::Python;
    use std::io::{Error as IoError, ErrorKind};
    use std::path::PathBuf;
    use tempfile::tempdir;

    #[test]
    fn test_managed_directory_new() -> PyResult<()> {
        Python::with_gil(|_py| {
            let temp = tempdir().unwrap();
            let base_dir = temp.path().to_str().unwrap();
            let dir = ManagedDirectory::new(base_dir, "test_dir", None, None)?;

            dir.create()?;
            assert_eq!(dir.n_digit, 4);
            assert_eq!(dir.idx, 0);
            assert!(dir.path.ends_with("test_dir"));
            assert!(dir.path.exists());

            Ok(())
        })
    }

    #[test]
    fn test_managed_directory_with_index() -> PyResult<()> {
        Python::with_gil(|_py| {
            let temp = tempdir().unwrap();
            let base_dir = temp.path().to_str().unwrap();
            let dir = ManagedDirectory::new(base_dir, "test_dir", Some(3), Some(1))?;
            dir.create()?;

            let expected_path = Path::new("divided").join("001").join("test_dir");

            assert!(dir.path.ends_with(&expected_path));
            assert!(dir.path.exists());

            Ok(())
        })
    }

    #[test]
    fn test_managed_directory_call() -> PyResult<()> {
        Python::with_gil(|_py| {
            let temp = tempdir().unwrap();
            let base_dir = temp.path().to_str().unwrap();
            let dir = ManagedDirectory::new(base_dir, "test_dir", None, None)?;

            let new_dir = dir.__call__(1)?;
            new_dir.create()?;
            let expected_path = Path::new("divided").join("0001").join("test_dir");

            assert!(new_dir.path.ends_with(&expected_path));
            assert!(new_dir.path.exists());

            let err = dir.__call__(-1);
            assert!(err.is_err());

            Ok(())
        })
    }

    #[test]
    fn test_managed_directory_list() -> PyResult<()> {
        Python::with_gil(|_py| {
            let temp = tempdir().unwrap();
            let base_dir = temp.path().to_str().unwrap();
            let dir = ManagedDirectory::new(base_dir, "test_dir", None, None)?;

            dir.create()?;

            let test_file = dir.path.join("test.txt");
            fs::write(&test_file, "test")
                .map_err(|e| PyIOError::new_err(format!("Failed to write test file: {}", e)))?;
            let files = dir.list()?;
            assert_eq!(files.len(), 1);
            assert!(files[0].contains("test.txt"));

            Ok(())
        })
    }

    #[test]
    fn test_managed_directory_string_representation() -> PyResult<()> {
        Python::with_gil(|_py| {
            let temp = tempdir().unwrap();
            let base_dir = temp.path().to_str().unwrap();
            let dir = ManagedDirectory::new(base_dir, "test_dir", None, None)?;

            assert!(dir.__str__().contains("test_dir"));
            assert!(dir.__repr__().starts_with("ManagedDirectory"));
            Ok(())
        })
    }

    #[test]
    fn test_managed_directory_path_without_create() -> PyResult<()> {
        Python::with_gil(|_py| {
            let temp = tempdir().unwrap();
            let base_dir = temp.path().to_str().unwrap();
            let dir = ManagedDirectory::new(base_dir, "test_dir", None, None)?;

            // パスを取得しても作成されないことを確認
            let path_str = dir.get_path()?;
            assert!(!Path::new(&path_str).exists());

            Ok(())
        })
    }

    #[test]
    fn test_directory_ops_new() -> PyResult<()> {
        Python::with_gil(|_py| {
            let temp = tempdir().unwrap();
            let base_dir = temp.path().to_str().unwrap();

            let ops = DirectoryOps::new(base_dir, None)?;
            assert_eq!(ops.n_digit, 4);
            assert!(ops.base_dir.exists());

            // カスタム桁数でインスタンス生成
            let ops_custom = DirectoryOps::new(base_dir, Some(6))?;
            assert_eq!(ops_custom.n_digit, 6);

            Ok(())
        })
    }

    #[test]
    fn test_directory_ops_getattr_creates_dir() -> PyResult<()> {
        Python::with_gil(|_py| {
            let temp = tempdir().unwrap();
            let base_dir = temp.path().to_str().unwrap();
            let ops = DirectoryOps::new(base_dir, None)?;

            let dir = ops.__getattr__("test_dir")?;
            assert!(!dir.path.exists());
            dir.create()?;
            assert!(dir.path.exists());

            Ok(())
        })
    }

    #[test]
    fn test_managed_directory_call_creates_divided() -> PyResult<()> {
        Python::with_gil(|_py| {
            let temp = tempdir().unwrap();
            let base_dir = temp.path().to_str().unwrap();
            let dir = ManagedDirectory::new(base_dir, "test_dir", None, None)?;

            // __call__でインデックス付きディレクトリが作成されることを確認
            let divided_dir = dir.__call__(1)?;
            assert!(divided_dir.path.exists());
            let expected_path = Path::new("divided").join("0001").join("test_dir");
            assert!(divided_dir.path.ends_with(&expected_path));

            // 元のディレクトリは作成されていないことを確認
            assert!(!dir.path.exists());

            Ok(())
        })
    }

    #[test]
    fn test_directory_ops_gettattr() -> PyResult<()> {
        Python::with_gil(|_py| {
            let temp = tempdir().unwrap();
            let base_dir = temp.path().to_str().unwrap();
            let ops = DirectoryOps::new(base_dir, None)?;

            let test_dir = ops.__getattr__("test_directory")?;
            test_dir.create()?;
            assert!(test_dir.path.exists());
            assert_eq!(test_dir.n_digit, 4);
            assert_eq!(test_dir.idx, 0);

            Ok(())
        })
    }

    #[test]
    fn test_directory_ops_repr() -> PyResult<()> {
        Python::with_gil(|_py| {
            let temp = tempdir().unwrap();
            let base_dir = temp.path().to_str().unwrap();
            let ops = DirectoryOps::new(base_dir, None)?;

            let repr = ops.__repr__();
            assert!(repr.contains("DirectoryOps"));
            assert!(repr.contains("n_digit=4"));
            assert!(repr.contains(base_dir));

            Ok(())
        })
    }

    #[test]
    fn test_directory_ops_all() -> PyResult<()> {
        Python::with_gil(|_py| {
            let temp = tempdir().unwrap();
            let base_dir = temp.path().to_str().unwrap();

            let ops = DirectoryOps::new(base_dir, Some(4))?;

            // 1. idx=None (no split)
            let result_no_idx = ops.all(None)?;
            for dir_name in &[
                "invoice",
                "invoice_patch",
                "attachment",
                "tasksupport",
                "structured",
                "meta",
                "thumbnail",
                "main_image",
                "other_image",
                "nonshared_raw",
                "raw",
            ] {
                assert!(
                    result_no_idx.iter().any(|item| {
                        item.ends_with(Path::new(dir_name).to_string_lossy().as_ref())
                    }),
                    "Directory not found: {}",
                    dir_name
                );
            }

            // 2
            let result_with_idx = ops.all(Some(2))?;
            for i in 1..=2 {
                let folder_name = format!("{:0width$}", i, width = 4);
                for div_dir in &[
                    "structured",
                    "meta",
                    "thumbnail",
                    "main_image",
                    "other_image",
                    "other_image",
                    "nonshared_raw",
                    "raw",
                ] {
                    let expected_segment = Path::new("divided")
                        .join(&folder_name)
                        .join(div_dir)
                        .to_string_lossy()
                        .to_string();
                    assert!(
                        result_with_idx
                            .iter()
                            .any(|item| item.contains(&expected_segment)),
                        "Divided directory not found: {}",
                        expected_segment
                    );
                }
            }
            Ok(())
        })
    }

    #[test]
    fn test_map_io_err_not_found() {
        Python::with_gil(|py| {
            let e = IoError::new(ErrorKind::NotFound, "some error message");
            let path = PathBuf::from("/not/found/path");
            let err = map_io_err(&e, "test_context", &path);

            assert!(err.is_instance_of::<PyFileNotFoundError>(py));

            let err_msg = err.to_string();
            assert!(err_msg.contains("File or directory not found"));
            assert!(err_msg.contains("/not/found/path"));
        });
    }

    #[test]
    fn test_map_io_err_permission_denied() {
        Python::with_gil(|py| {
            let e = IoError::new(ErrorKind::PermissionDenied, "some error message");
            let path = PathBuf::from("/some/protected/path");
            let err = map_io_err(&e, "perm context", &path);

            assert!(err.is_instance_of::<PyPermissionError>(py));

            let err_msg = err.to_string();
            assert!(err_msg.contains("Permission denied"));
            assert!(!err_msg.contains("/some/protected/path"));
        });
    }

    #[test]
    fn test_map_io_err_other() {
        Python::with_gil(|py| {
            let e = IoError::new(ErrorKind::Other, "some io error");
            let path = PathBuf::from("/path/to/other/error");
            let err = map_io_err(&e, "other context", &path);

            assert!(err.is_instance_of::<PyIOError>(py));

            let err_msg = err.to_string();
            assert!(err_msg.contains("An I/O error occurred."))
        })
    }
}
