import unittest
import logging

from planreview import esri, comment

# Set absolute file path for pytest
import sys, os
myPath = os.path.dirname(os.path.abspath(__file__))

# Add logging
logging.basicConfig(level=logging.DEBUG)

class TestESRI(unittest.TestCase):
    def test_geocode(self):
        """We can find our own office"""
        office = {
            "x": 1228858.540345859,
            "y": 151373.6873104528,
        }
        result = esri.geocode("701 WEST MARKHAM")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(office['x'],result['x'])
        self.assertAlmostEqual(office['y'],result['y'])

    def test_parcel_finder(self):
        """Parcels can be found by x-y coordinates"""
        office = {
            "x": 1228858.540345859,
            "y": 151373.6873104528,
        }
        acres = 0.48
        params = esri.params_from_loc(office)
        parcel_result = esri.fetch_parcel(params)
        self.assertIsNotNone(parcel_result)
        self.assertAlmostEqual(parcel_result.acres,acres,places=1)
    
    def test_parcel_finder2(self):
        """Parcels can be found by PID"""
        pid = "34L0200708100"
        acres = 0.48
        params = esri.params_from_pid(pid)
        parcel_result = esri.fetch_parcel(params)
        self.assertIsNotNone(parcel_result)
        self.assertAlmostEqual(parcel_result.acres,acres,places=1)

    def test_buffer(self):
        """Buffered ring produces sane results on trivial input"""
        in_ring = [
            [0.0,0.0],
            [0.0,1.0],
            [1.0,1.0],
            [1.0,0.0],
        ]
        target_ring = [
            [1.5,-0.5],
            [-0.5,-0.5],
            [-0.5,1.5],
            [1.5,1.5],
        ]
        result_ring = esri.buffer_ring(in_ring,0.5)
        for i,point in enumerate(target_ring):
            for j,_coord in enumerate(point):
                self.assertAlmostEqual(result_ring[i][j],target_ring[i][j],places=1)
    
    def test_buffer_realistic(self):
        """Buffer ring produces sane results on a real parcel."""
        from numpy import float64
        pulco_office = [
            [1229623,151187],
            [1229590,150990],
            [1229452,151014],
            [1229485,151211],
            [1229623,151187],
        ]
        result_ring = esri.buffer_ring(pulco_office,100)
        for x,y in result_ring:
            self.assertIsInstance(x,float64)
            self.assertIsInstance(y,float64)
            self.assertAlmostEqual(x,1229500,places=-4)
            self.assertAlmostEqual(y,151000,places=-4)

    
    def test_tracer(self):
        """ray tracer can find a point inside and outside a ring"""
        ring = [
            [1.0,1.0],
            [1.0,3.0],
            [3.0,3.0],
            [3.0,1.0],
        ]
        outer_point = [-2.0,1.0]
        inner_point = [1.5,1.5]
        self.assertTrue(esri.is_outside(ring,outer_point))
        self.assertFalse(esri.is_outside(ring,inner_point))

    def test_trace_origin(self):
        """ray tracer can find a point inside and outside a ring"""
        ring = [
            [0.0,0.0],
            [0.0,1.0],
            [1.0,1.0],
            [1.0,0.0],
        ]
        inner_point = [0.5,0.75]
        outer_point = [-0.5,1.0]
        self.assertTrue(esri.is_outside(ring,outer_point))
        self.assertFalse(esri.is_outside(ring,inner_point))

    def test_trans_null(self):
        """Transportation layer does not return information for minor streets.
        """
        office = [
            [1228929.53,151406.27],
            [1228904.93,151258.39],
            [1228766.98,151281.79],
            [1228791.58,151429.67],
            [1228929.53,151406.27],
        ]
        buffered_office = esri.buffer_ring(office,100)
        streets = esri.trans(buffered_office)
        self.assertIsNone(streets)
    
    def test_trans_pos(self):
        """We can get multiple streets from the transportation layer for
        properties at intersections.
        """
        pulco_office = [
            [1229623,151187],
            [1229590,150990],
            [1229452,151014],
            [1229485,151211],
            [1229623,151187],
        ]
        second_st = esri.Street("W 2ND ST","minor arterial",90,False, False)
        broadway_st = esri.Street("BROADWAY ST", "principal arterial", 110, True,True)
        buffered_office = esri.buffer_ring(pulco_office,100)
        streets = esri.trans(buffered_office)
        self.assertIsNotNone(streets)
        self.assertTrue(second_st in streets)
        self.assertTrue(broadway_st in streets)

    def test_zoning(self):
        """We can fetch design overlays, case files and zoning codes."""
        downtown_house = [
            [1232624.4,149087.92],
            [1232619.3,149006.58],
            [1232552.14,149018.27],
            [1232555.42,149099.93],
            [1232624.4,149087.92]
        ]
        zoning = esri.zoning(downtown_house)
        self.assertIsNotNone(zoning)
        self.assertTrue('Z-6734-B' in zoning.cases)
        self.assertTrue("R4A" in zoning.classification)
        self.assertTrue("MacArthur Park Historic District" in zoning.overlays)

    def test_flood(self):
        """We can detect floodplain and floodway within a single parcel."""
        lamar_porter = [
            [1219263,150840],
            [1219892,150808],
            [1219861,150185],
            [1219231,150219],
            [1219263,150840]
        ]
        flood_zones = esri.floodmap(lamar_porter)
        self.assertTrue("Floodway" in flood_zones)
        self.assertTrue("AE" in flood_zones)

class TestComment(unittest.TestCase):
    def test_base_renders(self):
        """base-comments renders successfully."""
        parcel = esri.ParcelData(
            {'x':1228857,'y':151362},
            [
                [1196800.21,157165.87],
                [1196785.61,157164.46],
                [1196773.0,157171.95],
                [1196634.99,157309.81],
                [1196804.34,157388.29],
                [1196950.88,157245.95],
                [1196918.36,157221.34],
                [1196882.2,157202.51],
                [1196800.21,157165.87]
            ],
            0.858314,
            esri.Envelope(1196634,157160,1196804,157388)
        )
        streets = [
            esri.Street("W MARKHAM ST","commercial",60,True,False),
        ]
        zoning = esri.Zone("UU",None,None)
        flooding = set()
        meta = comment.Meta()
        m = comment.Master(meta, parcel, streets, flooding, zoning)
        comments = comment.generate_base_comments(m)
        self.assertIsNotNone(comments)

    def test_email(self):
        """We can generate an email with trivial input."""
        comments = [
            "Eat your vegetables",
            "Brush your teeth",
            "Take out the trash"
        ]
        app = comment.Applicant(
            "Doug Funny",
            "Quail Man",
            "Mr. Funny",
            "",
            "Nickelodian",
            "Somewhere, USA 12345"
        )
        approved = True
        comments = comment.generate_email(comments,app,approved=approved)
        self.assertIsNotNone(comments)
    
    def test_pdf(self):
        """We can generate a comment letter with trivial input."""
        comments = [
            "You better watch out.",
            "You better not cry.",
            "You better not pout; I'm telling you why.",
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"*10
        ]
        applicant = comment.Applicant(
            "Abe Frohman, P.E.",
            "Sausage King of Chicago",
            "Mr. Frohman, sir",
            "Sausage Works Inc.",
            "123 Meat Lane",
            "Chicago, IL 12345"
        )
        approved = False
        destination = "junk.pdf"
        comment.generate_letter(comments,applicant,"Sausage Theme Park",destination,approved)
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()