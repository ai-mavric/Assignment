from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='FuelStation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('opis_id', models.IntegerField(db_index=True)),
                ('name', models.CharField(max_length=255)),
                ('address', models.CharField(max_length=255)),
                ('city', models.CharField(max_length=128)),
                ('state', models.CharField(max_length=2)),
                ('rack_id', models.IntegerField(blank=True, null=True)),
                ('price', models.DecimalField(decimal_places=4, help_text='Retail price, USD per gallon', max_digits=7)),
                ('lat', models.FloatField(blank=True, null=True)),
                ('lon', models.FloatField(blank=True, null=True)),
                ('geocode_source', models.CharField(blank=True, max_length=16)),
            ],
            options={
                'indexes': [models.Index(fields=['state', 'city'], name='routing_fue_state_217c0f_idx')],
            },
        ),
        migrations.CreateModel(
            name='Place',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('state', models.CharField(max_length=2)),
                ('name', models.CharField(help_text='Normalized name, see services.normalize', max_length=128)),
                ('display_name', models.CharField(max_length=128)),
                ('kind', models.CharField(choices=[('place', 'Place'), ('cousub', 'County subdivision')], max_length=8)),
                ('lat', models.FloatField()),
                ('lon', models.FloatField()),
            ],
            options={
                'indexes': [models.Index(fields=['state', 'name'], name='routing_pla_state_508609_idx')],
            },
        ),
    ]
