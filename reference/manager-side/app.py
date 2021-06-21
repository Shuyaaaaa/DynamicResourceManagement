from flask import Flask, render_template, redirect, url_for, jsonify,request,request
from manager import select_running_inst, create_new_instance, inst_remove, get_inst_info,inst_CPU,resize_worker_pool,ELB_DNS, inst_HTTP,get_detail, inst_HTTP, get_poolsize_laod, terminate_and_stop
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
from config import S3_BUCKET,S3_KEY,S3_SECRET, ELB_DNS, SQLALCHEMY_DATABASE_URI
import boto3
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
from auto_sacling import hanlder, CustimizedHandler
from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy import *
import logging

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

log = logging.getLogger('apscheduler.executors.default')
log.setLevel(logging.INFO)  # DEBUG

fmt = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
h = logging.StreamHandler()
h.setFormatter(fmt)
log.addHandler(h)

class User(db.Model): 
    id = db.Column(db.Integer, primary_key=True)  # id primary key
    username = db.Column(db.String(64), index=True, unique=True) # key Username 
    password_hash = db.Column(db.String(128))   # key password 
    storage = db.Column(db.String(300), index=True, unique=True)  # key storage 
    detectStorage = db.Column(db.String(300), index=True, unique=True)  # key which store the detected image path



s3 = boto3.client(
    's3',aws_access_key_id= S3_KEY,
    aws_secret_access_key= S3_SECRET
)
s3_resource = boto3.resource('s3')

scheduler = BackgroundScheduler()


@app.before_first_request
def auto_scale():
    scheduler.add_job(func=hanlder, trigger="interval", seconds=60)
    scheduler.start()



# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())



@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html', title='Home')

@app.before_first_request
def resize():
    resize_worker_pool()



@app.route('/workpool/<success>')
def pool(success):
    instance = select_running_inst()
    return render_template('userpool.html', title='user', instance_list = instance, success= success, load_balancer=ELB_DNS)



@app.route('/<instance_id>')
def view(instance_id):
    instance = get_detail(instance_id)
    time_list, cpu_list = inst_CPU(instance_id)
    list_time, http_list = inst_HTTP(instance_id)
    img = io.BytesIO()
    plt.plot(time_list,cpu_list, marker='*')
    plt.xlabel('Time (minutes)', fontsize=12)
    plt.ylabel('CPU utilization (%)', fontsize=12)
    plt.savefig(img, format='png')
    plt.close()
    img.seek(0)
    buffer = b''.join(img)
    b2 = base64.b64encode(buffer)
    sunalt2=b2.decode('utf-8')

    img2 = io.BytesIO()
    plt.plot(list_time,http_list, marker='*')
    plt.xlabel('Time (minutes)', fontsize=12)
    plt.ylabel('Http request(Count)', fontsize=12)
    plt.savefig(img2, format='png')
    plt.close()
    img2.seek(0)
    buffer2= b''.join(img2)
    b3 = base64.b64encode(buffer2)
    sunalt3=b3.decode('utf-8')


    return render_template('userdetail.html', instance = instance, sunalt=sunalt2, sunalt3=sunalt3)

@app.route('/<instanceid>')
def remove(instanceid):
    return render_template('userdetail.html')


@app.route('/add_worker')
def create_instance():
    success = create_new_instance()
    instance = select_running_inst()
    return redirect(url_for("pool", success=True))


@app.route("/remove/<remove_id>")
def remove_one(remove_id):
    inst_remove(remove_id)
    instance = select_running_inst()
    success = True
    return redirect(url_for("pool", success=success))


@app.route("/clear")
def clear_s3():
    bucket = s3_resource.Bucket(S3_BUCKET)
    bucket.objects.all().delete()
    db.session.query(User).delete()
    db.session.commit()
    return redirect(url_for("index"))



@app.route("/terminate")
def terminate():
    jobs = scheduler.get_jobs()
    jobs[0].remove()
    terminate_and_stop()
    return redirect(url_for("index"))


@app.route("/auto_modify", methods=['GET','POST'])
def auto_modify():
    if request.method == 'POST':
        jobs = scheduler.get_jobs()
        jobs[0].remove()
        threshold_max = request.form['threshold_max']
        threshold_min = request.form['threshold_min']
        ratio_expand  = request.form['ratio_expand']
        ratio_shrink = request.form['ratio_shrink']
        if threshold_max == '' or float(threshold_max) <= 0:
            threshold_max =80
        if threshold_min == '':
            threshold_min = 10
        if ratio_expand == '' or float(ratio_expand) <= 0:
            ratio_expand = 1.25
        if ratio_shrink == '' or float(ratio_shrink) <= 0:
            ratio_shrink = 0.75
        time.sleep(1)
        scheduler.add_job(lambda: CustimizedHandler(threshold_max,threshold_min,ratio_expand,ratio_shrink), trigger="interval", seconds=60)
        return render_template("auto_modify.html", success = True)
    else:
        return render_template("auto_modify.html")
 


@app.route("/auto")
def auto_check():
    x_axis, inst_num, CPU_utl = get_poolsize_laod()
    img = io.BytesIO()
    plt.plot(x_axis,inst_num, marker='*')
    plt.xlabel('Time (minutes)', fontsize=12)
    plt.ylabel('Instance number', fontsize=12)
    plt.savefig(img, format='png')
    plt.close()
    img.seek(0)
    buffer = b''.join(img)
    b2 = base64.b64encode(buffer)
    instance_num=b2.decode('utf-8')

    img2 = io.BytesIO()
    plt.plot(x_axis,CPU_utl, marker='*')
    plt.xlabel('Time (minutes)', fontsize=12)
    plt.ylabel('CPU utilization (%)', fontsize=12)
    plt.savefig(img2, format='png')
    plt.close()
    img2.seek(0)
    buffer2= b''.join(img2)
    b3 = base64.b64encode(buffer2)
    cpu_utl=b3.decode('utf-8')
    
    return render_template("auto.html", cpu_utl = cpu_utl, instance_num = instance_num)
