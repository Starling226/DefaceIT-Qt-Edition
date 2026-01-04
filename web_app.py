#!/usr/bin/env python3

import os
import uuid
from pathlib import Path
from flask import Flask, render_template, request, send_file, jsonify, url_for
from werkzeug.utils import secure_filename
import threading
import time

from video_blur_core import VideoBlurrer

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size
app.config['UPLOAD_FOLDER'] = '/app/uploads'
app.config['OUTPUT_FOLDER'] = '/app/outputs'

# Secret key for session management
# WARNING: Set SECRET_KEY environment variable in production!
secret_key = os.environ.get('SECRET_KEY')
if not secret_key:
    import sys
    import secrets
    # Generate a random key for development
    secret_key = secrets.token_hex(32)
    print("WARNING: No SECRET_KEY set. Using auto-generated key. Set SECRET_KEY environment variable in production!", file=sys.stderr)
app.config['SECRET_KEY'] = secret_key

ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv'}

# Store job statuses in memory
# NOTE: This is lost on restart. For production, consider Redis or database
jobs = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_video_task(job_id, input_path, output_path, settings):
    """Background task to process video"""
    try:
        jobs[job_id]['status'] = 'processing'
        jobs[job_id]['progress'] = 0
        
        def progress_callback(progress, fps, message):
            """Progress callback receives 3 parameters from VideoBlurrer"""
            jobs[job_id]['progress'] = int(progress)
            jobs[job_id]['message'] = message
            jobs[job_id]['fps'] = round(fps, 2) if fps > 0 else 0
        
        blurrer = VideoBlurrer(
            device=settings.get('device', 'auto'),
            blur_strength=settings.get('blur_strength', 51),
            blur_type=settings.get('blur_type', 'gaussian'),
            confidence=settings.get('confidence', 0.15),
            detect_faces=settings.get('detect_faces', True),
            detect_license_plates=settings.get('detect_license_plates', True),
            progress_callback=progress_callback,
            pitch_shift=settings.get('pitch_shift', 0.0)
        )
        
        blurrer.process_video(input_path, output_path)
        
        jobs[job_id]['status'] = 'completed'
        jobs[job_id]['progress'] = 100
        jobs[job_id]['output_file'] = os.path.basename(output_path)
        
    except Exception as e:
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['error'] = str(e)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    
    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
    
    # Create upload and output directories if they don't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
    
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    # Save uploaded file
    filename = secure_filename(file.filename)
    file_ext = filename.rsplit('.', 1)[1].lower()
    input_filename = f"{job_id}_input.{file_ext}"
    output_filename = f"{job_id}_output.{file_ext}"
    
    input_path = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)
    output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
    
    file.save(input_path)
    
    # Get settings from form
    settings = {
        'blur_strength': int(request.form.get('blur_strength', 51)),
        'confidence': float(request.form.get('confidence', 0.15)),
        'blur_type': request.form.get('blur_type', 'gaussian'),
        'detect_faces': request.form.get('detect_faces', 'true').lower() == 'true',
        'detect_license_plates': request.form.get('detect_license_plates', 'true').lower() == 'true',
        'device': request.form.get('device', 'auto'),
        'pitch_shift': float(request.form.get('pitch_shift', 0.0))
    }
    
    # Initialize job status
    jobs[job_id] = {
        'status': 'queued',
        'progress': 0,
        'input_file': filename,
        'created_at': time.time()
    }
    
    # Start background processing
    # Note: Using daemon threads for simplicity. For production, consider
    # a task queue like Celery for better job management and graceful shutdown
    thread = threading.Thread(
        target=process_video_task,
        args=(job_id, input_path, output_path, settings)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'job_id': job_id,
        'message': 'Video upload successful. Processing started.'
    })

@app.route('/status/<job_id>')
def get_status(job_id):
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = jobs[job_id]
    response = {
        'status': job['status'],
        'progress': job['progress'],
        'input_file': job['input_file']
    }
    
    if job['status'] == 'completed':
        response['download_url'] = url_for('download_file', job_id=job_id)
    elif job['status'] == 'failed':
        response['error'] = job.get('error', 'Unknown error')
    
    return jsonify(response)

@app.route('/download/<job_id>')
def download_file(job_id):
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = jobs[job_id]
    if job['status'] != 'completed':
        return jsonify({'error': 'Video processing not completed'}), 400
    
    output_filename = job['output_file']
    output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
    
    if not os.path.exists(output_path):
        return jsonify({'error': 'Output file not found'}), 404
    
    return send_file(
        output_path,
        as_attachment=True,
        download_name=f"blurred_{job['input_file']}"
    )

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
