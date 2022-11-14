import copy
import re

import modules.scripts as scripts
import gradio as gr

from PIL import ImageFont, ImageDraw
from fonts.ttf import Roboto
from modules import images
from modules.processing import Processed, process_images
from modules.shared import state, opts
import modules.sd_samplers

def trimPrompt(prompt):
    prompt = prompt.replace(", :", ":")
    prompt = re.sub(r"[, ]*\(:[\d.]+\)", "", prompt)
    prompt = re.sub(r"[, ]*[\(]+[\)]+", "", prompt)
    prompt = re.sub(r"^[, ]*", "", prompt)
    prompt = re.sub(r"[, ]*$", "", prompt)
    return prompt

def splitPrompt(prompt, skip=0, include_base=True):
    pattern = re.compile(r'[ ]*([\w ]+)([,]*)[ ]*')
    prompts = []

    if include_base:
        prompts.append(["", prompt])

    matches = list(re.finditer(pattern, prompt))

    for i in range(len(matches)):
        if i < skip:
            continue

        m = matches[i]
        if (len(m.group(1).strip()) > 1):
            prompts.append([m.group(1), trimPrompt(prompt.replace(m.group(0), ''))])
    
    return prompts

# This is a modified version of code from https://github.com/Extraltodeus/test_my_prompt/blob/main/test_my_prompt_custom_script.py
def write_on_image(img, msg):
    ix,iy = img.size
    draw = ImageDraw.Draw(img)
    margin=2
    fontsize=24
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(Roboto, fontsize)
    text_height=iy-60
    tx = draw.textbbox((0,0),msg,font)
    draw.text((int((ix-tx[2])/2),text_height+margin),msg,(0,0,0),font=font)
    draw.text((int((ix-tx[2])/2),text_height-margin),msg,(0,0,0),font=font)
    draw.text((int((ix-tx[2])/2+margin),text_height),msg,(0,0,0),font=font)
    draw.text((int((ix-tx[2])/2-margin),text_height),msg,(0,0,0),font=font)
    draw.text((int((ix-tx[2])/2),text_height), msg,(255,255,255),font=font)
    return img


class Script(scripts.Script):
    def title(self):
        return "Prompt puncher"

    def ui(self, is_img2img):
        info = gr.Label("This script will generate a grid of images with different parts of the prompt increased in strength. This can be used to find out what each part does to the image.")
        strength = gr.Slider(value=1.3, label="Strength", minimum=0, maximum=2, step=0.1)
        positives = gr.Checkbox(value=True, label="Include positive prompt")
        skip_first_positives = gr.Number(value=0, label="Skip first N parts of positive prompt")
        negatives = gr.Checkbox(value=False, label="Include negative prompt")        
        skip_first_negatives = gr.Number(value=0, label="Skip first N parts of negative prompt")
        return [info, strength, positives, skip_first_positives, negatives, skip_first_negatives]

    def run(self, p, info, strength, positives, skip_first_positives, negatives, skip_first_negatives):
        modules.processing.fix_seed(p)

        original_prompt = p.prompt[0] if type(p.prompt) == list else p.prompt
        prompts = splitPrompt(original_prompt, skip=skip_first_positives)
        original_negative_prompt = p.negative_prompt[0] if type(p.negative_prompt) == list else p.negative_prompt
        negative_prompts = splitPrompt(original_negative_prompt, skip=skip_first_negatives, include_base=positives == False)
        p.do_not_save_grid = True
        state.job_count = 0
        permutations = 0
        
        if positives:
            state.job_count += len(prompts) * p.n_iter
            permutations += len(prompts)
        
        if negatives:
            state.job_count += len(negative_prompts) * p.n_iter
            permutations += len(negative_prompts)
            
        print(f"Creating {permutations} image permutations")
        image_results = []
        all_prompts = []
        infotexts = []

        if positives:
            for prompt in prompts:
                copy_p = copy.copy(p)
                copy_p.prompt = prompt[1] if prompt[0] == "" else prompt[1] + f", ({prompt[0]}:{strength:.1f})"

                proc = process_images(copy_p)
                temp_grid = images.image_grid(proc.images, p.batch_size)
                temp_grid = write_on_image(temp_grid, "" if prompt[0] == "" else f"({prompt[0]}:{strength:.1f})")
                image_results.append(temp_grid)
                all_prompts += proc.all_prompts
                infotexts += proc.infotexts

        if negatives:
            for negative_prompt in negative_prompts:
                copy_p = copy.copy(p)
                copy_p.negative_prompt = negative_prompt[1] if negative_prompt[0] == "" else negative_prompt[1] + f", ({negative_prompt[0]}:{strength:.1f})"

                proc = process_images(copy_p)
                temp_grid = images.image_grid(proc.images, p.batch_size)
                temp_grid = write_on_image(temp_grid, "" if negative_prompt[0] == "" else f"!({negative_prompt[0]}:{strength:.1f})")
                image_results.append(temp_grid)
                all_prompts += proc.all_prompts
                infotexts += proc.infotexts

        grid = images.image_grid(image_results, p.batch_size)
        infotexts.insert(0, infotexts[0])
        image_results.insert(0, grid)
        images.save_image(grid, p.outpath_grids, "grid", grid=True, p=p)

        return Processed(p, image_results, p.seed, "", all_prompts=all_prompts, infotexts=infotexts)
