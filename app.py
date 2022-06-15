"""Visualize the results of a parametric study."""


import tempfile
import json
import zipfile
import shutil
import streamlit as st

from typing import List, Dict
from pathlib import Path
from plotly import graph_objects as go
from plotly.graph_objects import Figure
from pandas import DataFrame

from pollination_streamlit.api.client import ApiClient
from pollination_streamlit.interactors import Job
from pollination_streamlit_io import special

from viewer import render


def extract_eui(file_path: Path) -> float:
    """Extract EUI data from the eui.JSON file."""
    with open(file_path.as_posix(), 'r') as file:
        data = json.load(file)
        return data['eui']


def get_eui(job) -> List[float]:
    """Get a list of EUI data for each run of the job."""

    eui_folder = st.session_state.temp_folder.joinpath('eui')
    st.session_state.eui_folder = eui_folder
    if not eui_folder.exists():
        eui_folder.mkdir(parents=True, exist_ok=True)
    else:
        shutil.rmtree(eui_folder)
        eui_folder.mkdir(parents=True, exist_ok=True)

    runs = job.runs
    eui = []

    for run in runs:
        res_zip = run.download_zipped_output('eui')
        run_folder = eui_folder.joinpath(run.id)
        if not run_folder.exists():
            run_folder.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(res_zip) as zip_folder:
            zip_folder.extractall(run_folder.as_posix())

        eui_file = run_folder.joinpath('eui.json')
        eui.append(extract_eui(eui_file))

    return eui


def get_figure(df: DataFrame, eui: List[float]) -> Figure:
    """Prepare Plotly Parallel Coordinates plot."""

    dimension = [
        dict(label='Option-no', values=df['option-no']),
        dict(label='EUI', values=eui)
    ]

    if 'window-to-wall-ratio' in df.columns:
        dimension.append(
            dict(label='WWR', values=df['window-to-wall-ratio'].values, range=[0, 1]))
    if 'louver-count' in df.columns:
        dimension.append(
            dict(label='Louver count', values=df['louver-count'].values))
    if 'louver-depth' in df.columns:
        dimension.append(
            dict(label='Louver depth', values=df['louver-depth'].values))

    figure = go.Figure(data=go.Parcoords(
        line=dict(color='rgb(228, 61, 106)'), dimensions=dimension))

    figure.update_layout(
        font=dict(size=15)
    )

    return figure


@st.cache(allow_output_mutation=True)
def create_job(job_url: str) -> Job:
    """Create a Job object from a job URL."""
    url_split = job_url.split('/')
    job_id = url_split[-1]
    project = url_split[-3]
    owner = url_split[-5]

    return Job(owner, project, job_id, ApiClient())


@st.cache()
def download_models(job: Job) -> None:
    """Download HBJSON models from the job."""

    model_folder = st.session_state.temp_folder.joinpath('model')
    if not model_folder.exists():
        model_folder.mkdir(parents=True, exist_ok=True)
    else:
        shutil.rmtree(model_folder.as_posix())
        model_folder.mkdir(parents=True, exist_ok=True)

    artifacts = job.list_artifacts('inputs/model')
    for artifact in artifacts:
        hbjson_artifact = artifact.list_children()[0]
        hbjson_file = model_folder.joinpath(hbjson_artifact.name)
        hbjson_data = hbjson_artifact.download()
        hbjson_file.write_bytes(hbjson_data.read())

    st.session_state.model_folder = model_folder


def viz_lookup(df: DataFrame) -> None:
    """Create a dictionary to lookup downloaded HBJSON files for the job.

    This function creates a dictionary with the option-no as key and the
    Path to the HBJSON file as value structure. This is dictionary is used to
    render the HBJSON associated with an option-no in the viewer.
    """
    viz_dict: Dict[str, Path] = {}
    for count, item in enumerate(df['option-no'].values):
        viz_dict[item] = st.session_state.model_folder.joinpath(
            df['model'][count].split('/')[-1])

    st.session_state.viz_dict = viz_dict


def main():

    host = special.get_host(key='get_host')
    if not host:
        host = 'web'
    st.session_state.host = host

    message = 'Paste URL of job with parametric runs using the annual energy recipe.'

    job_url = st.text_input(
        message,
        value='https://app.pollination.cloud/devang/projects/demo/jobs/3e6bef53-179b-4fc4-aeed-03e49816e5e8')

    if not job_url:
        st.error(message)
        return

    job = create_job(job_url)

    if job.recipe.name.lower() != 'annual-energy-use':
        st.error(
            'This app only works with the [Annual Energy Use recipe](https://app.pollination.cloud/ladybug-tools/recipes/custom-energy-sim/0.3.11).')
        return

    if 'temp_folder' not in st.session_state:
        st.session_state.temp_folder = Path(tempfile.mkdtemp())

    # streamlit fails to hash a _json.Scanner object so we need to use a conditional
    # here to not run get_eui on each referesh
    if 'eui' not in st.session_state:
        eui = get_eui(job)
        st.session_state.eui = eui

    download_models(job)
    df = job.runs_dataframe.dataframe
    viz_lookup(df)

    figure = get_figure(df, st.session_state.eui)
    st.plotly_chart(figure)

    option_num = st.text_input('Option number', value='')
    if option_num:
        try:
            render(st.session_state.viz_dict[option_num])
        except (ValueError, KeyError):
            st.error('Not a valid option number.')


if __name__ == '__main__':
    main()
