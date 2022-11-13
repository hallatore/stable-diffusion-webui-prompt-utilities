import copy
import re

import modules.scripts as scripts
import gradio as gr

from modules import images
from modules.processing import Processed, process_images
from modules.shared import state, opts
import modules.sd_samplers

original_label = "ORIGINAL"

def trimPrompt(prompt):
    prompt = prompt.replace(", :", ":")
    prompt = re.sub(r"[, ]*\(:[\d.]+\)", "", prompt)
    prompt = re.sub(r"[, ]*[\(]+[\)]+", "", prompt)
    prompt = re.sub(r"^[, ]*", "", prompt)
    prompt = re.sub(r"[, ]*$", "", prompt)
    return prompt

def splitPrompt(prompt, include_base=True):
    pattern = re.compile(r'[ ]*([\w ]+)([,]*)[ ]*')
    prompts = []

    if include_base:
        prompts.append([original_label, prompt])

    for m in re.finditer(pattern, prompt):
        if (len(m.group(1).strip()) > 1):
            prompts.append([m.group(1), trimPrompt(prompt.replace(m.group(0), ''))])
    
    return prompts


class Script(scripts.Script):
    def title(self):
        return "Prompt puncher"

    def ui(self, is_img2img):
        info = gr.Label("This script will generate a grid of images with different parts of the prompt increased in strength. This can be used to find out what each part does to the image.")
        strength = gr.Slider(value=1.3, label="Strength", minimum=0, maximum=2, step=0.1)
        positives = gr.Checkbox(value=True, label="Include positive prompt")
        negatives = gr.Checkbox(value=False, label="Include negative prompt")
        return [info, strength, positives, negatives]

    def run(self, p, info, strength, positives, negatives):
        modules.processing.fix_seed(p)

        original_prompt = p.prompt[0] if type(p.prompt) == list else p.prompt
        prompts = splitPrompt(original_prompt)
        original_negative_prompt = p.negative_prompt[0] if type(p.negative_prompt) == list else p.negative_prompt
        negative_prompts = splitPrompt(original_negative_prompt, include_base=positives == False)
        p.do_not_save_grid = True
        state.job_count = 0
        
        if positives:
            state.job_count += len(prompts) * p.n_iter
        
        if negatives:
            state.job_count += len(negative_prompts) * p.n_iter

        image_results = []
        all_prompts = []
        infotexts = []

        if positives:
            for prompt in prompts:
                copy_p = copy.copy(p)
                copy_p.prompt = prompt[1] if prompt[0] == original_label else prompt[1] + f", ({prompt[0]}:{strength:.1f})"

                proc = process_images(copy_p)
                temp_grid = images.image_grid(proc.images, p.batch_size)
                annotation = f"({original_label})" if prompt[0] == original_label else f"({prompt[0]}:{strength:.1f})"
                temp_grid = images.draw_grid_annotations(temp_grid, temp_grid.width, temp_grid.height, hor_texts=[[images.GridAnnotation(annotation, is_active=True)]], ver_texts=[[images.GridAnnotation()]])
                image_results.append(temp_grid)

                all_prompts += proc.all_prompts
                infotexts += proc.infotexts

                if opts.grid_save:
                    images.save_image(temp_grid, p.outpath_grids, "grid", grid=True, p=copy_p)

        if negatives:
            for negative_prompt in negative_prompts:
                copy_p = copy.copy(p)
                copy_p.negative_prompt = negative_prompt[1] if negative_prompt[0] == original_label else negative_prompt[1] + f", ({negative_prompt[0]}:{strength:.1f})"

                proc = process_images(copy_p)
                temp_grid = images.image_grid(proc.images, p.batch_size)
                annotation = f"({original_label})" if negative_prompt[0] == original_label else f"({negative_prompt[0]}:{strength:.1f})"
                temp_grid = images.draw_grid_annotations(temp_grid, temp_grid.width, temp_grid.height, hor_texts=[[images.GridAnnotation(annotation, is_active=True)]], ver_texts=[[images.GridAnnotation()]])
                image_results.append(temp_grid)

                all_prompts += proc.all_prompts
                infotexts += proc.infotexts

                if opts.grid_save:
                    images.save_image(temp_grid, p.outpath_grids, "grid", grid=True, p=copy_p)

        grid = images.image_grid(image_results, p.batch_size)
        all_prompts.insert(0, p.prompt)
        image_results.insert(0, grid)

        if opts.grid_save:
            images.save_image(grid, p.outpath_grids, "grid", grid=True, p=p)

        return Processed(p, image_results, p.seed, "", all_prompts=all_prompts, infotexts=infotexts)
