import shutil
from pathlib import Path

import fitz

BASE_IMAGE_DIR=(
    Path(__file__).resolve().parents[1]
    /"data"
    /"extracted_images"
)


def get_image_storage_dir(user_id :str,md5:str):
    directory = BASE_IMAGE_DIR / str(user_id) / str(md5)
    directory.mkdir(parents=True,exist_ok=True)
    return directory


def get_image_file_path(user_id : str,md5 :str,filename :str,):
    return BASE_IMAGE_DIR / str(user_id) / str(md5) / filename

def extract_images_from_pdf(pdf_path :str,user_id :str,md5:str):
    pdf_file = Path(pdf_path)

    if not pdf_file.is_file():
        return {}

    output_dir = get_image_storage_dir(user_id, md5)
    result: dict[int,list[str]] = {}

    try:
        pdf = fitz.open(str(pdf_file))
    except Exception:
        return {}

    try:
        for page_number in range(len(pdf)):
            page = pdf[page_number]
            page_images : list[str] = []

            for image_index,image_info in enumerate(page.get_images(full=True)):
                xref = image_info[0]

                try:
                    image_data = pdf.extract_image(xref) #从PDF内部提取图片
                    image_bytes = image_data["image"]
                    extension = image_data["ext"]#文件后缀

                    filename = (
                        f"p{page_number}_i{image_index}.{extension}"
                    )
                    target = output_dir / filename
                    target.write_bytes(image_bytes)

                    page_images.append(filename)

                except Exception:
                    continue

            result[page_number] = page_images
    finally:
        pdf.close()

    return result


def delete_image_directory(user_id:str,md5:str):
    directory = BASE_IMAGE_DIR / str(user_id) / str(md5)
    if not directory.exists():
        return False

    shutil.rmtree(directory)
    return True


def delete_user_all_images(user_id:str):
    directory = BASE_IMAGE_DIR / str(user_id)
    if not directory.exists():
        return False

    shutil.rmtree(directory)
    return True