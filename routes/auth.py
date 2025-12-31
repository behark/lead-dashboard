from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, UserRole

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember', False)
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account is disabled.', 'danger')
                return render_template('auth/login.html')
            
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.index'))
        
        flash('Invalid username or password.', 'danger')
    
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # Only allow registration if no users exist (first user becomes admin)
    # Or if current user is admin
    user_count = User.query.count()
    
    if user_count > 0 and (not current_user.is_authenticated or current_user.role != UserRole.ADMIN):
        flash('Registration is disabled. Contact an administrator.', 'warning')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return render_template('auth/register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('auth/register.html')
        
        # First user becomes admin
        role = UserRole.ADMIN if user_count == 0 else UserRole.SALES
        
        user = User(username=username, email=email, role=role)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful. Please login.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', first_user=(user_count == 0))


@auth_bp.route('/users')
@login_required
def users():
    if current_user.role != UserRole.ADMIN:
        flash('Access denied.', 'danger')
        return redirect(url_for('main.index'))
    
    users = User.query.all()
    return render_template('auth/users.html', users=users)


@auth_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required
def toggle_user(user_id):
    if current_user.role != UserRole.ADMIN:
        flash('Access denied.', 'danger')
        return redirect(url_for('main.index'))
    
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Cannot disable your own account.', 'warning')
    else:
        user.is_active = not user.is_active
        db.session.commit()
        flash(f"User {'enabled' if user.is_active else 'disabled'}.", 'success')
    
    return redirect(url_for('auth.users'))


@auth_bp.route('/users/<int:user_id>/role', methods=['POST'])
@login_required
def change_role(user_id):
    if current_user.role != UserRole.ADMIN:
        flash('Access denied.', 'danger')
        return redirect(url_for('main.index'))
    
    user = User.query.get_or_404(user_id)
    new_role = request.form.get('role')
    
    try:
        user.role = UserRole(new_role)
        db.session.commit()
        flash('Role updated.', 'success')
    except ValueError:
        flash('Invalid role.', 'danger')
    
    return redirect(url_for('auth.users'))
