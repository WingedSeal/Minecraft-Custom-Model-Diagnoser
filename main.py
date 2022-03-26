from collections import defaultdict
from datetime import datetime
import os
import shutil
import sys
from pathlib import Path
from getpass import getpass
from json import JSONDecodeError, dump, dumps, load
import traceback


BOT_NAME = '[WingedSeal-Bot] '
INDENT_LV = 4
DEFAULTS = {
    "pack_format": 8,
    "description": "Fixed by WingedSeal-Bot"
}
AUTO_FIX = False
is_error_exist = False


class NoQuickFix(Exception):
    pass


class ResourcePackError(Exception):
    pass


def ask(question: str) -> bool:
    global is_error_exist
    is_error_exist = True
    print(BOT_NAME+question)
    print(BOT_NAME+"Quick-fix is avaliable. Would you like me to try to fix it? (yes/no)")
    if AUTO_FIX:
        return True
    while True:
        answer = input().lower()
        if answer in ['yes', 'y']:
            return True
        elif answer in ['no', 'n']:
            return False
        else:
            print(
                BOT_NAME+"I can't understand your answer, please type either 'yes' or 'no'.")


def fix_name(string: str) -> tuple[bool, str]:
    if string.islower() and ' ' not in string:
        return (False, string)
    if ask(f"I found invalid file name({string}). I can fix that for you right now."):
        return True, string.replace(' ', '_').lower()
    return False, string


def check_pack_mcmeta(path: Path) -> None:
    DEFAULT_JSON = {"pack": {
                    "pack_format": DEFAULTS["pack_format"], "description": DEFAULTS["description"]}}
    with (path/'pack.mcmeta').open('r') as file:
        try:
            json = load(file)
        except JSONDecodeError:
            if ask("I found an error in JSON format of `pack.mcmeta`. I can reset it."):
                with (path/'pack.mcmeta').open('w+') as file:
                    dump(DEFAULT_JSON, file, indent=INDENT_LV)
                return
        if 'pack' not in json:
            if ask("I can't find `pack` keyword in `pack.mcmeta`. I can reset it."):
                with (path/'pack.mcmeta').open('w+') as file:
                    dump(DEFAULT_JSON, file, indent=INDENT_LV)
                return
        if "pack_format" not in json['pack']:
            if ask(f"I can't find `pack_format` keyword in `pack.mcmeta`. I can set it to {DEFAULTS['pack_format']}"):
                json['pack']['pack_format'] = DEFAULTS['pack_format']
        else:
            try:
                assert type(json['pack']['pack_format']) == int
            except (ValueError, AssertionError):
                if ask(f"`pack_format` in `pack.mcmeta` should be a whole number. I can set it to {DEFAULTS['pack_format']}"):
                    json['pack']['pack_format'] = DEFAULTS['pack_format']

        if "description" not in json['pack']:
            if ask(f"I can't find `description` keyword in `pack.mcmeta`. I can set it to {DEFAULTS['description']}"):
                json['pack']['description'] = DEFAULTS['description']
        with (path/'pack.mcmeta').open('w+') as file:
            dump(json, file, indent=INDENT_LV)


def check_non_json(file_path: Path) -> None:
    if file_path.suffix != '.json':
        if ask(f"I found `{file_path.name}` file which isn't json file. Would you like me to change that?"):
            if file_path.stem.endswith(".json"):
                file_path.rename(Path(file_path.parent, file_path.stem))
            else:
                file_path.rename(
                    Path(file_path.parent, file_path.stem+'.json'))


def check_non_png(file_path: Path) -> None:
    if file_path.suffix != '.png':
        if ask(f"I found `{file_path.name}` file which isn't png file. Would you like me to change that?"):
            if file_path.stem.endswith(".json"):
                file_path.rename(Path(file_path.parent, file_path.stem))
            else:
                file_path.rename(
                    Path(file_path.parent, file_path.stem+'.png'))


def check_json_error(file_path: Path) -> dict[str, str]:
    with file_path.open('r') as file:
        try:
            json = load(file)
        except JSONDecodeError as error:
            raise NoQuickFix(
                f"I can't read {file_path.resolve().as_posix()} json file. It's malformed. Here's the error:\n{error}")
    return json


def check_vanilla_json(file_path: Path, json: dict[str, str]) -> str:
    if "overrides" not in json:
        raise NoQuickFix(
            f"I can't find `overrides` key in {file_path.resolve().as_posix()}.")
    if not isinstance(json["overrides"], list):
        raise NoQuickFix(
            f"`overrides` value is not an array(list) in {file_path.resolve().as_posix()}.")
    try:
        json["overrides"][0]["predicate"]["custom_model_data"]
        custom_model_data = [override["predicate"]["custom_model_data"]
                             for override in json["overrides"]]
    except KeyError as error:
        raise NoQuickFix(error.args[0])

    last_custom_model_data = -1
    for number in custom_model_data:
        if number == last_custom_model_data:
            raise NoQuickFix(
                f"Duplicate custom_model_data({number}) in {file_path.resolve().as_posix()}.")

        last_custom_model_data = number
    sorted_overrides = sorted(
        json["overrides"], key=lambda x: x["predicate"]["custom_model_data"])
    if json["overrides"] != sorted_overrides and ask(f"custom_model_data is not in ascending order in {file_path.resolve().as_posix()}. I can rearrange them, would you like me to?"):
        json["overrides"] = sorted_overrides
        with file_path.open('w+') as file:
            dump(json, file, indent=INDENT_LV)

    for index in range(len(json["overrides"])):
        _, json["overrides"][index]["model"] = fix_name(
            json["overrides"][index]["model"])

    return [override["model"]
            for override in json["overrides"]]


def check_custom_json(file_path: Path, json: dict[str, str]) -> str:
    if not isinstance(json["textures"], dict):
        raise NoQuickFix(
            f"value of `textures` is not JSON in {file_path.resolve().as_posix()} You did not export it from BlockBench properly. (Or any other tool you are using)")
    if "elements" not in json:
        raise NoQuickFix(
            f"`elements` key not found in {file_path.resolve().as_posix()}. You did not export it from BlockBench properly. (Or any other tool you are using)")
    if '"#missing' in dumps(json):
        raise NoQuickFix(
            f"`#missing` texture found in {file_path.resolve().as_posix()}. You did not give texture file to BlockBench properly.")

    fixed_textures = {key: fix_name(texture)[1]
                      for key, texture in json["textures"].items()}
    if json["textures"] != fixed_textures and ask(f"Invalid textures file found in {file_path.resolve().as_posix()} I think I can fix it."):
        json["textures"] = fixed_textures
        with file_path.open('w+') as file:
            dump(json, file, indent=INDENT_LV)
    return json["textures"].values()


def is_vanilla_json(file_path: Path, json: dict[str, str]) -> bool:
    if "textures" not in json:
        raise ResourcePackError(
            f"I can't find `textures` key in {file_path.resolve().as_posix()}. You did not export it from BlockBench properly. (Or any other tool you are using)")
    return ("parent" in json and
            "layer0" in json["textures"] and
            json["textures"]["layer0"] == f"item/{file_path.stem}"
            )


def check_files(path: Path) -> None:
    model_dir = path/'assets'/'minecraft'/'models'
    item_dir = model_dir/'item'
    if not item_dir.is_dir():
        raise ResourcePackError(
            "`assets/minecraft/models/item` not found. I don't know how to handle this. I'm not made for 2d resourcepacks")
    texture_dir = path/'assets'/'minecraft'/'textures'
    if not texture_dir.is_dir():
        raise ResourcePackError(
            "`assets/minecraft/textures` not found. I don't know how to handle this. Something isn't right.")

    set_of_model_file: set[str] = set()
    set_of_model_key: set[str] = set()

    set_of_textures_file: set[str] = set()
    set_of_textures_key: set[str] = set()

    for file_path in texture_dir.glob('**/*'):
        if not file_path.is_file():
            continue
        check_non_png(file_path)
        is_new, new_name = fix_name(
            file_path.relative_to(path).as_posix())
        if is_new:
            file_path.rename(path/new_name)
        set_of_textures_file.add(file_path.relative_to(
            texture_dir).parent.as_posix()+'/'+file_path.stem)

    for file_path in item_dir.glob('**/*'):
        if not file_path.is_file():
            continue
        check_non_json(file_path)
        json = check_json_error(file_path)

        is_new, new_name = fix_name(
            file_path.relative_to(path).as_posix())
        if is_new:
            file_path.rename(path/new_name)

        if is_vanilla_json(file_path, json):
            for model in check_vanilla_json(file_path, json):
                set_of_model_key.add(model)
        else:
            set_of_model_file.add(file_path.relative_to(
                model_dir).parent.as_posix()+'/'+file_path.stem)
            for texture in check_custom_json(file_path, json):
                set_of_textures_key.add(texture)

    strings = []
    if (diff := set_of_model_key-set_of_model_file):
        strings.append(
            f"File not found for model keys: {diff}")
    if (diff := set_of_model_file-set_of_model_key):
        strings.append(
            f"Unused model files: {[f'{stem}.json' for stem in diff]!r}")
    if (diff := set_of_textures_key-set_of_textures_file):
        strings.append(
            f"File not found for texture keys: {diff}")
    if (diff := set_of_textures_file-set_of_textures_key):
        strings.append(
            f"Unused texture files: {[f'{stem}.png' for stem in diff]!r}")
    if strings:
        raise NoQuickFix("I got some unmatched names...\n"+'\n'.join(strings))


def _diagnose(path: Path, is_backup: bool = False):
    global AUTO_FIX
    if not (path/'pack.mcmeta').is_file():
        raise ResourcePackError(
            "I can't find `pack.mcmeta`. Are you sure this is the correct folder?")
    if not (path/'assets'/'minecraft').is_dir():
        raise ResourcePackError(
            "I can't find `assets/minecraft`. Are you sure this is the correct folder?")
    if is_backup:
        backup(path)

    print(BOT_NAME+"Do you want me to automatically fix everything for you? (yes/no)")
    while True:
        answer = input().lower()
        if answer in ['yes', 'y']:
            AUTO_FIX = True
            break
        elif answer in ['no', 'n']:
            AUTO_FIX = False
            break
        else:
            print(
                BOT_NAME+"I can't understand your answer, please type either 'yes' or 'no'.")

    check_pack_mcmeta(path)
    check_files(path)

    if is_error_exist:
        print(BOT_NAME+"That should be everything, try reloading the resourcepack with `F3+T` and see if it works~")
    else:
        print(BOT_NAME+"Sorry, I can't find a single error in your resourcepack...")


def backup(path: Path) -> None:
    print(BOT_NAME+"Let me backup your resourcepack real quick.")
    time_str = datetime.now().strftime("%Y%m%d-%H%M%S")
    assets_folder = path/'assets'
    backup_assets_folder = path/'backup'/time_str/'assets'
    pack_meta = path/'pack.mcmeta'
    backup_pack_meta = path/'backup'/time_str/'pack.mcmeta'
    shutil.copytree(assets_folder, backup_assets_folder)
    shutil.copyfile(pack_meta, backup_pack_meta)
    print(BOT_NAME+"I'm done coppying, let's start.")


def diagnose(path: Path):
    try:
        _diagnose(path.parent, is_backup=True)
    except ResourcePackError as error:
        print(BOT_NAME+error.args[0])
        getpass("Press enter to exit...")
    except NoQuickFix as error:
        global is_error_exist
        is_error_exist = True
        print(BOT_NAME+error.args[0])
        print(BOT_NAME+"No quick-fix is avaliable. I cannot fix this part.")
        print(BOT_NAME+"Fix this part yourself and try again.")
        getpass("Press enter to try again...")
        diagnose()
    except Exception as error:
        print(BOT_NAME+"My creator messed up again. Send him this:\n")
        traceback.print_exc()
        getpass("Press enter to exit...")


def main():
    diagnose(Path(sys.argv[0]))


if __name__ == '__main__':
    main()
