use image::imageops::FilterType;
use image::{DynamicImage, ImageBuffer, Rgba};
use pyo3::exceptions;
use pyo3::prelude::*;
use std::fs;
use std::path::Path;

#[pyfunction]
pub fn resize_image_aspect_ratio(
    input_path: String,
    output_path: String,
    width: u32,
    height: u32,
) -> PyResult<()> {
    if width == 0 || height == 0 {
        return Err(exceptions::PyValueError::new_err(
            "Width and height must be greater than zero",
        ));
    }

    const MAX_DIMENSION: u32 = 10_000;
    if width > MAX_DIMENSION || height > MAX_DIMENSION {
        return Err(exceptions::PyValueError::new_err(format!(
            "Width and height must not exceed {MAX_DIMENSION}."
        )));
    }

    let target_size = (width, height);

    let input = Path::new(&input_path);
    let output = Path::new(&output_path);

    let img_ret = image::open(input);
    let img: DynamicImage = match img_ret {
        Ok(image) => image,
        Err(e) => {
            return Err(exceptions::PyIOError::new_err(format!(
                "Failed to load image: {e}"
            )));
        }
    };
    let img_ratio = img.width() as f32 / img.height() as f32;
    let target_ratio = target_size.0 as f32 / target_size.1 as f32;

    let (new_width, new_height) = if img_ratio > target_ratio {
        (target_size.0, (target_size.0 as f32 / img_ratio) as u32)
    } else {
        ((target_size.1 as f32 * img_ratio) as u32, target_size.1)
    };
    let resized_img = img.resize_exact(new_width, new_height, FilterType::Lanczos3);

    let color_type = img.color();

    let x = (target_size.0 - new_width) / 2;
    let y = (target_size.1 - new_height) / 2;
    let new_img = match color_type {
        image::ColorType::Rgb8 => {
            let mut dynamic_img =
                ImageBuffer::from_pixel(target_size.0, target_size.1, image::Rgb([255, 255, 255]));
            let resized_dynamic_img = resized_img.to_rgb8();
            image::imageops::overlay(&mut dynamic_img, &resized_dynamic_img, x.into(), y.into());
            DynamicImage::ImageRgb8(dynamic_img)
        }
        image::ColorType::Rgba8 => {
            let mut dynamic_img =
                ImageBuffer::from_pixel(target_size.0, target_size.1, Rgba([255, 255, 255, 255]));
            let resized_dynamic_img = resized_img.to_rgba8();
            image::imageops::overlay(&mut dynamic_img, &resized_dynamic_img, x.into(), y.into());
            DynamicImage::ImageRgba8(dynamic_img)
        }
        _ => {
            return Err(exceptions::PyValueError::new_err(format!(
                "Unsupported color type: {color_type:?}"
            )));
        }
    };

    match new_img.save(output) {
        Ok(_) => Ok(()),
        Err(e) => {
            // Copy original image if save fails.
            if let Err(copy_e) = fs::copy(input, output) {
                Err(exceptions::PyIOError::new_err(format!(
                    "Failed to save the image or copy the original image. {copy_e}"
                )))
            } else {
                Err(exceptions::PyIOError::new_err(format!(
                    "Resizing failed, but I copied the original image. {e}"
                )))
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use image::{RgbImage, RgbaImage};
    use std::fs;
    use std::io::Write;
    use std::path::{Path, PathBuf};

    fn get_test_dir() -> PathBuf {
        let current_dir = std::env::current_dir().expect("Failed to get current directory");
        let project_root = current_dir
            .ancestors()
            .find(|ancestor| ancestor.join("Cargo.toml").exists())
            .expect("Faild to find project root");
        project_root.join("tests").join("images")
    }

    fn setup_test_files() -> Vec<PathBuf> {
        let test_dir = get_test_dir();
        let test_files = vec![
            test_dir.join("test_cos_640_480.png"),
            test_dir.join("test_sin_300_300.png"),
            test_dir.join("test_tan_1080_480.png"),
        ];
        test_files
    }

    fn setup_dummy_test_txtfile(input_path: &PathBuf) {
        let content = "This is a dummy text file for testing";

        let mut file = fs::File::create(input_path).expect("Failed to create test file!");
        file.write_all(content.as_bytes())
            .expect("cannot write to file!");
    }

    fn teardown_test_file(file: &PathBuf) {
        if file.exists() {
            fs::remove_file(&file).expect("Faild to remove test file");
        }
    }

    fn create_sample_image(path: &str, width: u32, height: u32, color_type: image::ColorType) {
        match color_type {
            image::ColorType::Rgb8 => {
                let img = RgbImage::from_pixel(width, height, image::Rgb([128, 128, 128]));
                img.save(path).expect("Failed to save image");
            }
            image::ColorType::Rgba8 => {
                let img = RgbaImage::from_pixel(width, height, image::Rgba([128, 128, 128, 255]));
                img.save(path).expect("Failed to save image");
            }
            _ => {
                panic!("Unsupported color type");
            }
        }
    }

    #[test]
    fn test_resize_success() {
        // Prepare Python Runtime
        pyo3::prepare_freethreaded_python();

        let test_files = setup_test_files();
        for input_path in test_files {
            let input_path_str = input_path
                .to_str()
                .expect("Failed to convert path to string")
                .to_string();

            let filename = input_path.file_name().unwrap().to_str().unwrap();
            let output_filename = format!("output_success_{}", filename);
            let output_path = get_test_dir().join(&output_filename);
            let output_path_str = output_path
                .to_str()
                .expect("Failed to convert path to string")
                .to_string();

            let width = 640;
            let height = 480;

            if Path::new(&output_path).exists() {
                fs::remove_file(&output_path).expect("Faild to remove test file");
            }

            let ret = resize_image_aspect_ratio(
                input_path_str.clone(),
                output_path_str.clone(),
                width,
                height,
            );
            // Check if the function returned Ok
            assert!(ret.is_ok(), "resize function failed");
            // Check if the output file exists
            assert!(
                Path::new(&output_path_str).exists(),
                "Failed to save resized image"
            );

            let img = image::open(&output_path_str).expect("Cannot open the output image");
            assert_eq!(
                img.width(),
                width,
                "Output image width differs from expected value"
            );
            assert_eq!(
                img.height(),
                height,
                "Output image height differs from expected value"
            );
            fs::remove_file(&output_path_str).expect("Unable to delete output image");
        }
    }

    // Negative case 1: Test when input file does not exist
    #[test]
    fn test_resize_non_existent_inputfile() {
        // Prepare Python Runtime
        pyo3::prepare_freethreaded_python();

        let test_dir = get_test_dir();
        let input_path = test_dir.join("non_existent_file.png");
        let output_path = test_dir.join("output_failure_non_existent_file.png");
        let input_path_str = input_path
            .to_str()
            .expect("Failed to convert path to string")
            .to_string();
        let output_path_str = output_path
            .to_str()
            .expect("Failed to convert path to string")
            .to_string();
        let width = 640;
        let height = 480;

        if output_path.exists() {
            fs::remove_file(&output_path).expect("Faild to remove test file");
        }

        let ret = resize_image_aspect_ratio(
            input_path_str.clone(),
            output_path_str.clone(),
            width,
            height,
        );

        assert!(
            ret.is_err(),
            "resize function should return an error when input file does not exist"
        );

        assert!(
            !output_path.exists(),
            "Output file should not be created when input file does not exist"
        );
    }

    // Negative case 2: Test when the input file is an invalid image file
    #[test]
    fn test_resize_invalid_image() {
        pyo3::prepare_freethreaded_python();

        // setup test files
        let test_dir = get_test_dir();
        let input_path = test_dir.join("invalid_image.txt");
        let output_path = test_dir.join("output_invalid_image.jpg");
        let input_path_str = input_path
            .to_str()
            .expect("Failed to convert path to string")
            .to_string();
        let output_path_str = output_path
            .to_str()
            .expect("Failed to convert path to string")
            .to_string();
        let width = 640;
        let height = 480;
        setup_dummy_test_txtfile(&input_path);

        if output_path.exists() {
            fs::remove_file(&output_path).expect("Faild to remove test file");
        }

        // test
        let ret = resize_image_aspect_ratio(
            input_path_str.clone(),
            output_path_str.clone(),
            width,
            height,
        );

        assert!(
            ret.is_err(),
            "resize function should return an error when input file is not an image file"
        );
        assert!(
            !output_path.exists(),
            "Output file should not be created when input file is not an image file"
        );

        // tear down
        teardown_test_file(&input_path);
    }

    #[test]
    // Negative case 3: Test for zero width or height when resizing
    fn test_resize_zero_dimensions() {
        pyo3::prepare_freethreaded_python();

        let test_dir = get_test_dir();
        let test_files = setup_test_files();

        for input_path in &test_files {
            let input_path_str = input_path
                .to_str()
                .expect("Failed to convert path to string")
                .to_string();

            let filename = input_path.file_name().unwrap().to_str().unwrap();
            let output_filename = format!("output_failure_zero_dimensions_{}", filename);
            let output_path = test_dir.join(&output_filename);
            let output_path_str = output_path
                .to_str()
                .expect("Failed to convert path to string")
                .to_string();

            let width = 0;
            let height = 480;

            if output_path.exists() {
                fs::remove_file(&output_path).expect("Faild to remove test file");
            }

            let ret = resize_image_aspect_ratio(
                input_path_str.clone(),
                output_path_str.clone(),
                width,
                height,
            );

            assert!(
                ret.is_err(),
                "resize function should return an error when width is zero"
            );

            assert!(
                !output_path.exists(),
                "Output file should not be created when width is zero",
            );
        }
    }

    // Negative case 4: Test for very large widths and heights
    #[test]
    fn test_exceeding_max_dimensions() {
        pyo3::prepare_freethreaded_python();

        let test_dir = get_test_dir();
        let test_file_path = test_dir.join("test_cos_640_480.png");
        let test_output_path = test_dir.join("test_output_large.png");
        let input_path_str = test_file_path
            .to_str()
            .expect("Failed to convert path to string")
            .to_string();
        let test_output_path_str = test_output_path
            .to_str()
            .expect("Failed to convert path to string")
            .to_string();
        let max_dimension = 10_000;
        let target_width = max_dimension + 1;
        let target_height = max_dimension + 1;

        let result = resize_image_aspect_ratio(
            input_path_str.clone(),
            test_output_path_str.clone(),
            target_width,
            target_height,
        );
        assert!(result.is_err());
        if let Err(e) = result {
            assert!(e.to_string().contains("Width and height must not exceed"));
        }

        assert!(!test_output_path.exists());
    }

    // Negative case 5:
    #[test]
    fn test_different_image_formats() {
        let test_dir = get_test_dir();
        let formats = vec![
            (
                test_dir.join("test_input_format.png"),
                test_dir.join("test_output_format.png"),
                image::ColorType::Rgba8,
            ),
            (
                test_dir.join("test_input_format.jpg"),
                test_dir.join("test_output_format.jpg"),
                image::ColorType::Rgb8,
            ),
            (
                test_dir.join("test_input_format.bmp"),
                test_dir.join("test_output_format.bmp"),
                image::ColorType::Rgb8,
            ),
        ];
        let target_width = 640;
        let target_height = 480;

        for (input_path, output_path, color_type) in &formats {
            let input_path_str = input_path
                .to_str()
                .expect("Failed to convert path to string")
                .to_string();
            let output_path_str = output_path
                .to_str()
                .expect("Failed to convert path to string")
                .to_string();

            create_sample_image(&input_path_str, 800, 600, *color_type);

            resize_image_aspect_ratio(
                input_path_str.clone(),
                output_path_str.clone(),
                target_width,
                target_height,
            )
            .unwrap();

            assert!(Path::new(output_path).exists());

            let output_img = image::open(output_path).unwrap();
            assert_eq!(output_img.width(), target_width);
            assert_eq!(output_img.height(), target_height);

            fs::remove_file(input_path).expect("Unable to delete input image");
            fs::remove_file(output_path).expect("Unable to delete output image");
        }
    }

    // Resize alpha-channeled images
    #[test]
    fn test_alpha_channel_preservation() {
        let test_dir = get_test_dir();
        let input_path = test_dir.join("test_input_alpha.png");
        let output_path = test_dir.join("test_output_alpha.png");
        let input_path_str = input_path
            .to_str()
            .expect("Failed to convert path to string")
            .to_string();
        let output_path_str = output_path
            .to_str()
            .expect("Failed to convert path to string")
            .to_string();

        let target_width = 640;
        let target_height = 480;

        create_sample_image(&input_path_str, 800, 600, image::ColorType::Rgba8);

        resize_image_aspect_ratio(
            input_path_str.clone(),
            output_path_str.clone(),
            target_width,
            target_height,
        )
        .unwrap();

        assert!(output_path.exists());

        let output_img = image::open(&output_path).unwrap();
        assert_eq!(output_img.width(), target_width);
        assert_eq!(output_img.height(), target_height);

        fs::remove_file(input_path).expect("Unable to delete input image");
        fs::remove_file(output_path).expect("Unable to delete output image");
    }
}
