"""A module to add a Pollination 3D viewer to the app."""

import streamlit as st
from pathlib import Path
from honeybee_vtk.model import Model as VTKModel
from pollination_streamlit_viewer import viewer
from honeybee.model import Model as HBModel
from pollination_streamlit_io import button, inputs


@st.cache()
def create_vtkjs(hb_model_path: Path) -> Path:
    if not hb_model_path:
        return

    model = VTKModel.from_hbjson(hb_model_path.as_posix())

    vtkjs_folder = st.session_state.temp_folder.joinpath('vtkjs')
    if not vtkjs_folder.exists():
        vtkjs_folder.mkdir(parents=True, exist_ok=True)

    vtkjs_file = vtkjs_folder.joinpath(f'{hb_model_path.stem}.vtkjs')
    if not vtkjs_file.is_file():
        model.to_vtkjs(
            folder=vtkjs_folder.as_posix(),
            name=hb_model_path.stem
        )

    return vtkjs_file


def rhino_hbjson(hb_model: HBModel, bake: bool = True) -> None:
    """Visualize and bake HBJSON in rhino."""

    if bake:
        col1, col2 = st.columns(2)

        with col1:
            inputs.send(
                data=hb_model.to_dict(),
                is_pollination_model=True,
                default_checked=True,
                label='View model',
                unique_id='unique-id-02',
                key='architext option',
            )

        with col2:
            button.send(
                'BakePollinationModel',
                hb_model.to_dict(),
                'bake-geometry-key',
                options={
                    "layer": "hbjson",
                    "units": "Meters"
                },
                key='bake-geometry',
            )
    else:
        inputs.send(
            data=hb_model.to_dict(),
            is_pollination_model=True,
            default_checked=True,
            label='View model',
            unique_id='unique-id-02',
            key='architext option',
        )


def render(hb_model_path: Path, key='3d_viewer', subscribe=False, bake=True):
    """Render HBJSON."""

    if st.session_state.host.lower() == 'rhino':
        hb_model = HBModel.from_hbjson(hb_model_path.as_posix())
        rhino_hbjson(hb_model, bake=bake)
    else:
        vtkjs_name = f'{hb_model_path.stem}_vtkjs'

        if vtkjs_name not in st.session_state:
            vtkjs = create_vtkjs(hb_model_path)
            viewer(content=vtkjs.read_bytes(),
                   key=key, subscribe=subscribe)
            st.session_state[vtkjs_name] = vtkjs
        else:
            viewer(content=st.session_state[vtkjs_name].read_bytes(),
                   key=key, subscribe=subscribe)
