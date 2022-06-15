"""Visualize the results of a parametric study."""

import streamlit as st
import tempfile
import json
import zipfile
from pollination_streamlit.selectors import job_selector
from pollination_streamlit.api.client import ApiClient
from plotly import graph_objects as go
from typing import List, Tuple
from pathlib import Path
from pollination_streamlit.interactors import Job, Run, Recipe
from queenbee.job.job import JobStatusEnum
from enum import Enum
from viewer import render
from pollination_streamlit_io import special
import shutil


class SimStatus(Enum):
    NOTSTARTED = 0
    INCOPLETE = 1
    COMPLETE = 2
    FAILED = 3
    CANCELLED = 4


def request_status(job: Job) -> SimStatus:

    if job.status.status in [
            JobStatusEnum.pre_processing,
            JobStatusEnum.running,
            JobStatusEnum.created,
            JobStatusEnum.unknown]:
        return SimStatus.INCOPLETE

    elif job.status.status == JobStatusEnum.failed:
        return SimStatus.FAILED

    elif job.status.status == JobStatusEnum.cancelled:
        return SimStatus.CANCELLED

    else:
        return SimStatus.COMPLETE


def extract_eui(file_path: Path) -> float:
    with open(file_path.as_posix(), 'r') as file:
        data = json.load(file)
        return data['eui']


def json_scanner_hash(obj):
    return obj.json()


def get_eui(job) -> List[float]:
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


def get_figure(df, eui):

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
def create_job(job_url):
    url_split = job_url.split('/')
    job_id = url_split[-1]
    project = url_split[-3]
    owner = url_split[-5]

    return Job(owner, project, job_id, ApiClient())


def download_models(job):
    model_folder = st.session_state.temp_folder.joinpath('model')
    st.session_state.model_folder = model_folder
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


def viz_dict(df):
    viz_dict = {}
    for count, item in enumerate(df['option-no'].values):
        viz_dict[item] = st.session_state.model_folder.joinpath(
            df['model'][count].split('/')[-1])

    st.session_state.viz_dict = viz_dict


@st.cache(suppress_st_warning=True)
def download(job):
    eui = get_eui(job)

    df = job.runs_dataframe.dataframe

    download_models(job)
    viz_dict(df)

    st.session_state.eui = eui
    st.session_state.df = df


def main():

    host = special.get_host(key='get_host')
    if not host:
        host = 'web'
    st.session_state.host = host
    st.session_state.status = None

    job_url = st.text_input(
        'Job URL', value='https://app.pollination.cloud/devang/projects/demo/jobs/3e6bef53-179b-4fc4-aeed-03e49816e5e8')
    job = create_job(job_url)

    if job and 'temp_folder' not in st.session_state:
        st.session_state.temp_folder = Path(tempfile.mkdtemp())

    download(job)

    figure = get_figure(st.session_state.df, st.session_state.eui)
    st.plotly_chart(figure)
    option_num = st.text_input('Option number', value='')
    if option_num:
        try:
            render(st.session_state.viz_dict[option_num])
        except (ValueError, KeyError):
            st.error('Not a valid option number.')


if __name__ == '__main__':
    main()
