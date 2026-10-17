import PyInstaller.__main__
import os

if __name__ == '__main__':
    # Determine the directory of the current script
    project_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.join(project_dir, "frontend")
    
    import shutil
    import zipfile
    
    # Run PyInstaller with the required arguments
    PyInstaller.__main__.run([
        'main.py',
        '--name=RepoGen-S7-Setup', # Output name
        '--windowed',  # No console window
        '--onefile',   # Single executable
        f'--add-data={frontend_dir}{os.pathsep}frontend',
        '--clean',
        '--noconfirm',
    ])
    
    dist_dir = os.path.join(project_dir, 'dist')
    old_exe = os.path.join(dist_dir, 'RepoGen-S7.exe')
    if os.path.exists(old_exe):
        os.remove(old_exe)
        
    setup_exe = os.path.join(dist_dir, 'RepoGen-S7-Setup.exe')
    readme_path = os.path.join(dist_dir, 'README.txt')
    
    # Create portable zip
    zip_path = os.path.join(dist_dir, 'RepoGen-Portable.zip')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        if os.path.exists(setup_exe):
            zipf.write(setup_exe, 'RepoGen-S7-Setup.exe')
        if os.path.exists(readme_path):
            zipf.write(readme_path, 'README.txt')
            
    print("Build complete. Official installer and portable zip are in 'dist' directory.")
