use pyo3::prelude::*;
use pyo3::wrap_pyfunction;
mod charset_detector;
mod dag;
mod fsops;
mod imageutil;

#[pymodule]
pub fn _core(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(
        imageutil::processing::resize_image_aspect_ratio,
        module
    )?)?;

    module.add_function(wrap_pyfunction!(charset_detector::detect_encoding, module)?)?;

    module.add_function(wrap_pyfunction!(
        charset_detector::read_file_with_encoding,
        module
    )?)?;

    module.add_class::<fsops::ManagedDirectory>()?;
    module.add_class::<fsops::DirectoryOps>()?;
    // RustDAG is intentionally NOT registered: dag.rs is frozen (ADR-020),
    // internal-only, and not on any v2.0 critical path.

    Ok(())
}
