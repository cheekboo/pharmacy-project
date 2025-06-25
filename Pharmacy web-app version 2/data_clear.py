@app.route('/clear_db')
def clear_db():
    db = get_db()
    db.execute('DELETE FROM users')
    db.execute('DELETE FROM medicines')
    db.execute('DELETE FROM orders')
    db.commit()
    return "All data has been cleared from the database."
#http://localhost:5000/clear_db