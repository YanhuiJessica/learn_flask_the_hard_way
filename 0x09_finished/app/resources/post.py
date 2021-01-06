from flask import request, current_app
from flask_login import current_user
from flask_restful import Resource, reqparse

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from datetime import datetime
from pathlib import Path

from marshmallow.exceptions import ValidationError

from app.post.models import Post
from app.extensions import marshmallow, db
from app.utils.paginate import paginate
from app.utils.watermark import embed_watermark, extract_watermark

class PostSchema(marshmallow.SQLAlchemyAutoSchema):

    id = marshmallow.Int(dump_only=True)

    class Meta:
        model = Post
        sql_session = db.session

class PostExtract(Resource):

    def get(self, post_id):
        schema = PostSchema()
        post = Post.query.get_or_404(post_id)
        image_path = str(Path(current_app.config['UPLOAD_FOLDER']) / schema.dump(post)['image'])
        e_text = extract_watermark(image_path)
        return {"extract_text": e_text}

class PostResource(Resource):
    # method_decorators = [jwt_required]

    def get(self, post_id):
        schema = PostSchema()
        post = Post.query.get_or_404(post_id)
        return {"post": schema.dump(post)}

    def put(self, post_id):
        schema = PostSchema(partial=True)
        post = Post.query.get_or_404(post_id)
        try:
            # instance: Optional existing instance to modify
            update_value = schema.load(request.json, instance=post)
            Post.query.filter_by(id=post_id).update(update_value)
        except ValidationError:
            return 422

        db.session.commit()

        return {"msg": "post updated", "post": schema.dump(post)}

    def delete(self, post_id):
        schema = PostSchema()
        post = Post.query.get_or_404(post_id)
        db.session.delete(post)
        db.session.commit()

        import os
        os.remove(str(Path(current_app.config['UPLOAD_FOLDER']) / schema.dump(post)['image']))

        return {"msg": "post deleted"}


post_parser = reqparse.RequestParser()
post_parser.add_argument('text', type=str, location='form')
post_parser.add_argument('watermark', type=str, location='form')
post_parser.add_argument('image', type=FileStorage, location='files')


class PostList(Resource):
    # method_decorators = [jwt_required]

    def get(self):
        schema = PostSchema(many=True)
        query = Post.query
        return paginate(query, schema)

    def post(self):
        schema = PostSchema()

        args = post_parser.parse_args()

        text = args.get('text')
        if text is None:
            text = ''

        image = args.get('image')
        if image.filename == '':
            return {'msg': 'you must post file.'}, 422

        file_name = str(int(datetime.now().timestamp() *
                            1000)) + '-' + secure_filename(image.filename)

        image_path = str(Path(current_app.config['UPLOAD_FOLDER']) / file_name)
        image.save(image_path)

        watermark = args.get('watermark')
        if watermark:
            embed_watermark(image_path, watermark, image_path)

        post = Post(user_id=current_user.id,
                    user_name=current_user.name,
                    text=text,
                    image=file_name)

        db.session.add(post)
        db.session.commit()

        return {"msg": "post created", "post": schema.dump(post)}, 201